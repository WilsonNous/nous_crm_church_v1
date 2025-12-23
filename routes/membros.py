import logging
from flask import Blueprint, jsonify, request, render_template
from database import get_db_connection

# ============================================================
# BLUEPRINT
# ============================================================
bp_membros = Blueprint("membros", __name__)

# ============================================================
# HELPERS
# ============================================================
def fetch_all_dict(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ============================================================
# ROTAS
# ============================================================

# ------------------------------------------------------------
# 1) API — LISTAGEM / BUSCA DE MEMBROS
# ------------------------------------------------------------
@bp_membros.route("/api/membros", methods=["GET"])
def listar_membros():
    try:
        termo = request.args.get("q", "").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        if termo:
            like = f"%{termo}%"
            cursor.execute("""
                SELECT
                    id_membro,
                    nome,
                    telefone,
                    email,
                    cidade,
                    estado,
                    estado_civil,
                    status_membro,
                    data_cadastro
                FROM membros
                WHERE nome LIKE %s
                   OR telefone LIKE %s
                ORDER BY nome
                LIMIT 500;
            """, (like, like))
        else:
            cursor.execute("""
                SELECT
                    id_membro,
                    nome,
                    telefone,
                    email,
                    cidade,
                    estado,
                    estado_civil,
                    status_membro,
                    data_cadastro
                FROM membros
                ORDER BY nome
                LIMIT 500;
            """)

        membros = fetch_all_dict(cursor)

        cursor.close()
        conn.close()

        return jsonify({"membros": membros}), 200

    except Exception as e:
        logging.exception(e)
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------
# 2) TELA HTML — LISTAGEM DE MEMBROS
# ------------------------------------------------------------
@bp_membros.route("/membros", methods=["GET"])
def tela_membros():
    return render_template("membros.html")


# ============================================================
# REGISTRO DO BLUEPRINT
# ============================================================
def register(app):
    app.register_blueprint(bp_membros)
