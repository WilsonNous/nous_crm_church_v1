import logging
from flask import Blueprint, jsonify, request
from database import get_db_connection

# ============================================================
# BLUEPRINT
# ============================================================
bp_membros = Blueprint("membros", __name__)

# ============================================================
# REGISTER (obrigatório para routes/__init__.py)
# ============================================================
def register(app):
    """
    Função padrão chamada pelo routes/__init__.py
    """
    app.register_blueprint(bp_membros)
    logging.info("✅ Blueprint membros registrado com sucesso.")

# ============================================================
# HELPERS
# ============================================================
def fetch_all_dict(cursor):
    """
    Converte resultado de cursor NORMAL (tuple) em lista de dicts
    """
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
        if not conn:
            logging.error("❌ Falha ao obter conexão com o banco (membros).")
            return jsonify({
                "status": "error",
                "error": "Erro de conexão com o banco de dados"
            }), 500

        cursor = conn.cursor()  # cursor NORMAL (tuple)

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

        logging.info(f"📋 {len(membros)} membros retornados (filtro='{termo}')")

        return jsonify({
            "status": "success",
            "total": len(membros),
            "membros": membros
        }), 200

    except Exception as e:
        logging.exception("❌ Erro ao listar membros")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500
