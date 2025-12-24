import logging
from flask import Blueprint, jsonify, request, render_template
from database import get_db_connection

bp_membros = Blueprint("membros", __name__)

# ============================================================
# HELPERS
# ============================================================
def fetch_all_dict(cursor):
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]

# ============================================================
# API — LISTAGEM / BUSCA DE MEMBROS
# ============================================================
@bp_membros.route("/api/membros", methods=["GET"])
def listar_membros():
    try:
        termo = request.args.get("q", "").strip()

        conn = get_db_connection()
        cursor = conn.cursor()  # ✅ cursor NORMAL

        sql = """
            SELECT
                id_membro AS id,
                nome,
                telefone,
                email,
                cidade,
                estado,
                estado_civil,
                status_membro,
                data_cadastro
            FROM membros
            WHERE 1=1
        """
        params = []

        if termo:
            sql += " AND (nome LIKE %s OR telefone LIKE %s)"
            like = f"%{termo}%"
            params.extend([like, like])

        sql += " ORDER BY nome LIMIT 500"

        cursor.execute(sql, params)
        membros = fetch_all_dict(cursor)

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "total": len(membros),
            "membros": membros
        }), 200

    except Exception as e:
        logging.exception(e)
        return jsonify({"status": "error", "error": str(e)}), 500
