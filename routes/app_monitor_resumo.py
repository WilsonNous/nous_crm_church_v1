import logging
from flask import Blueprint, jsonify, request
from database import get_db_connection

monitor_resumo_bp = Blueprint("app_monitor_resumo_bp", __name__)


def register(app):
    app.register_blueprint(monitor_resumo_bp)


@monitor_resumo_bp.route('/api/monitor/resumo', methods=['GET'])
def monitor_resumo():
    try:
        date_filter = (request.args.get('date') or '').strip()
        search_filter = (request.args.get('q') or '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        filters = []
        params = []

        if date_filter:
            filters.append("DATE(c.data_hora) = %s")
            params.append(date_filter)

        if search_filter:
            like = f"%{search_filter}%"
            filters.append("(v.nome LIKE %s OR v.telefone LIKE %s OR c.mensagem LIKE %s)")
            params.extend([like, like, like])

        where_sql = ""
        if filters:
            where_sql = " AND " + " AND ".join(filters)

        # A mesma seleção filtrada alimenta métricas e prévia. ROW_NUMBER escolhe
        # a mensagem mais recente de cada visitante sem gerar uma query adicional
        # para cada linha do resumo (evita o antigo padrão N+1).
        query = f"""
            WITH mensagens_filtradas AS (
                SELECT
                    v.id AS visitante_id,
                    v.nome AS visitante_nome,
                    v.telefone,
                    c.id AS conversa_id,
                    c.mensagem,
                    c.tipo,
                    c.data_hora,
                    ROW_NUMBER() OVER (
                        PARTITION BY v.id
                        ORDER BY c.data_hora DESC, c.id DESC
                    ) AS rn
                FROM visitantes v
                JOIN conversas c ON c.visitante_id = v.id
                WHERE 1 = 1{where_sql}
            ),
            resumo AS (
                SELECT
                    visitante_id,
                    MAX(visitante_nome) AS visitante_nome,
                    MAX(telefone) AS telefone,
                    COUNT(*) AS total_mensagens,
                    SUM(CASE WHEN LOWER(tipo) = 'recebida' THEN 1 ELSE 0 END) AS recebidas,
                    SUM(CASE WHEN LOWER(tipo) = 'enviada' THEN 1 ELSE 0 END) AS enviadas,
                    MIN(data_hora) AS primeira_mensagem,
                    MAX(data_hora) AS ultima_mensagem
                FROM mensagens_filtradas
                GROUP BY visitante_id
            )
            SELECT
                r.visitante_id,
                r.visitante_nome,
                r.telefone,
                r.total_mensagens,
                r.recebidas,
                r.enviadas,
                r.primeira_mensagem,
                r.ultima_mensagem,
                mf.mensagem AS ultima_mensagem_texto,
                mf.tipo AS ultimo_tipo
            FROM resumo r
            JOIN mensagens_filtradas mf
              ON mf.visitante_id = r.visitante_id
             AND mf.rn = 1
            ORDER BY r.ultima_mensagem DESC
            LIMIT 300
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []

        conversas = []
        for row in rows:
            conversas.append({
                "visitante_id": row["visitante_id"],
                "visitante_nome": row.get("visitante_nome") or "Sem nome",
                "telefone": row.get("telefone") or "",
                "total_mensagens": int(row.get("total_mensagens") or 0),
                "recebidas": int(row.get("recebidas") or 0),
                "enviadas": int(row.get("enviadas") or 0),
                "primeira_mensagem": row["primeira_mensagem"].isoformat() if row.get("primeira_mensagem") else None,
                "ultima_mensagem": row["ultima_mensagem"].isoformat() if row.get("ultima_mensagem") else None,
                "ultima_mensagem_texto": row.get("ultima_mensagem_texto") or "",
                "ultimo_tipo": row.get("ultimo_tipo") or ""
            })

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "total": len(conversas),
            "conversas": conversas
        }), 200

    except Exception as e:
        logging.error(f"Erro em /api/monitor/resumo: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
