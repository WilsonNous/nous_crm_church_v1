import logging
from flask import Blueprint, jsonify, request
from database import get_db_connection

monitor_resumo_bp = Blueprint("app_monitor_resumo_bp", __name__)


def register(app):
    app.register_blueprint(monitor_resumo_bp)


@monitor_resumo_bp.route('/api/monitor/resumo', methods=['GET'])
def monitor_resumo():
    conn = None
    cursor = None
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

        # Compatível com versões antigas de MySQL/MariaDB: evita CTE e
        # ROW_NUMBER. A subconsulta correlacionada retorna a última mensagem
        # dentro do MESMO conjunto filtrado, sem executar N+1 no Python.
        preview_filters = []
        preview_params = []

        if date_filter:
            preview_filters.append("DATE(c2.data_hora) = %s")
            preview_params.append(date_filter)

        if search_filter:
            like = f"%{search_filter}%"
            preview_filters.append("(v2.nome LIKE %s OR v2.telefone LIKE %s OR c2.mensagem LIKE %s)")
            preview_params.extend([like, like, like])

        preview_where = ""
        if preview_filters:
            preview_where = " AND " + " AND ".join(preview_filters)

        query = f"""
            SELECT
                v.id AS visitante_id,
                v.nome AS visitante_nome,
                v.telefone,
                COUNT(c.id) AS total_mensagens,
                SUM(CASE WHEN LOWER(c.tipo) = 'recebida' THEN 1 ELSE 0 END) AS recebidas,
                SUM(CASE WHEN LOWER(c.tipo) = 'enviada' THEN 1 ELSE 0 END) AS enviadas,
                MIN(c.data_hora) AS primeira_mensagem,
                MAX(c.data_hora) AS ultima_mensagem,
                (
                    SELECT c2.mensagem
                    FROM conversas c2
                    JOIN visitantes v2 ON v2.id = c2.visitante_id
                    WHERE c2.visitante_id = v.id{preview_where}
                    ORDER BY c2.data_hora DESC, c2.id DESC
                    LIMIT 1
                ) AS ultima_mensagem_texto,
                (
                    SELECT c3.tipo
                    FROM conversas c3
                    JOIN visitantes v3 ON v3.id = c3.visitante_id
                    WHERE c3.visitante_id = v.id{preview_where.replace('c2.', 'c3.').replace('v2.', 'v3.')}
                    ORDER BY c3.data_hora DESC, c3.id DESC
                    LIMIT 1
                ) AS ultimo_tipo
            FROM visitantes v
            JOIN conversas c ON c.visitante_id = v.id
            WHERE 1 = 1{where_sql}
            GROUP BY v.id, v.nome, v.telefone
            ORDER BY MAX(c.data_hora) DESC
            LIMIT 300
        """

        # A consulta possui os filtros da prévia duas vezes (texto e tipo),
        # seguidos pelos filtros do agrupamento principal.
        all_params = preview_params + preview_params + params
        cursor.execute(query, tuple(all_params))
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

        return jsonify({
            "status": "success",
            "total": len(conversas),
            "conversas": conversas
        }), 200

    except Exception as e:
        logging.error(f"Erro em /api/monitor/resumo: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
