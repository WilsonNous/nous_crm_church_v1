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

        query = """
            SELECT
                v.id AS visitante_id,
                v.nome AS visitante_nome,
                v.telefone,
                COUNT(c.id) AS total_mensagens,
                SUM(CASE WHEN LOWER(c.tipo) = 'recebida' THEN 1 ELSE 0 END) AS recebidas,
                SUM(CASE WHEN LOWER(c.tipo) = 'enviada' THEN 1 ELSE 0 END) AS enviadas,
                MIN(c.data_hora) AS primeira_mensagem,
                MAX(c.data_hora) AS ultima_mensagem
            FROM visitantes v
            JOIN conversas c ON c.visitante_id = v.id
            WHERE 1 = 1
        """
        params = []

        if date_filter:
            query += " AND DATE(c.data_hora) = %s"
            params.append(date_filter)

        if search_filter:
            like = f"%{search_filter}%"
            query += " AND (v.nome LIKE %s OR v.telefone LIKE %s OR c.mensagem LIKE %s)"
            params.extend([like, like, like])

        query += """
            GROUP BY v.id, v.nome, v.telefone
            ORDER BY MAX(c.data_hora) DESC
            LIMIT 300
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []

        conversas = []
        for row in rows:
            cursor.execute("""
                SELECT mensagem, tipo
                FROM conversas
                WHERE visitante_id = %s
                ORDER BY data_hora DESC, id DESC
                LIMIT 1
            """, (row["visitante_id"],))
            ultima = cursor.fetchone() or {}

            conversas.append({
                "visitante_id": row["visitante_id"],
                "visitante_nome": row.get("visitante_nome") or "Sem nome",
                "telefone": row.get("telefone") or "",
                "total_mensagens": int(row.get("total_mensagens") or 0),
                "recebidas": int(row.get("recebidas") or 0),
                "enviadas": int(row.get("enviadas") or 0),
                "primeira_mensagem": row["primeira_mensagem"].isoformat() if row.get("primeira_mensagem") else None,
                "ultima_mensagem": row["ultima_mensagem"].isoformat() if row.get("ultima_mensagem") else None,
                "ultima_mensagem_texto": ultima.get("mensagem") or "",
                "ultimo_tipo": ultima.get("tipo") or ""
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
