import logging
from flask import Blueprint, jsonify, request
from database import get_db_connection

bp_membros = Blueprint("membros", __name__)

# ============================================================
# HELPERS
# ============================================================
def fetch_all_dict(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []

    columns = [col[0] for col in cursor.description]
    return [
        {columns[i]: row[i] for i in range(len(columns))}
        for row in rows
    ]


def fetch_one_dict(cursor):
    row = cursor.fetchone()
    if not row:
        return {}

    columns = [col[0] for col in cursor.description]
    return {columns[i]: row[i] for i in range(len(columns))}

# ============================================================
# 1) API — LISTAGEM / BUSCA DE MEMBROS
# ============================================================
@bp_membros.route("/api/membros", methods=["GET"])
def listar_membros():
    try:
        termo = request.args.get("q", "").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

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
        return jsonify({"error": str(e)}), 500

# ============================================================
# 2) API — ESTATÍSTICAS DE MEMBROS
# ============================================================
@bp_membros.route("/api/membros/estatisticas", methods=["GET"])
def estatisticas_membros():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # TOTAL
        cursor.execute("SELECT COUNT(*) AS total FROM membros;")
        total = fetch_one_dict(cursor)

        # GÊNERO
        cursor.execute("""
            SELECT
                SUM(genero='masculino') AS homens,
                SUM(genero='feminino') AS mulheres,
                COUNT(*) AS total
            FROM membros;
        """)
        genero = fetch_one_dict(cursor)

        # ESTADO CIVIL
        cursor.execute("""
            SELECT
                COALESCE(estado_civil, 'Não informado') AS estado_civil,
                COUNT(*) AS total
            FROM membros
            GROUP BY estado_civil
            ORDER BY total DESC;
        """)
        estado_civil = fetch_all_dict(cursor)

        # NOVO COMEÇO
        cursor.execute("""
            SELECT
                SUM(novo_comeco = 1) AS fizeram,
                SUM(novo_comeco = 0) AS nao_fizeram
            FROM membros;
        """)
        novo_comeco = fetch_one_dict(cursor)

        # CLASSE DE MEMBROS
        cursor.execute("""
            SELECT
                SUM(classe_membros = 1) AS fizeram,
                SUM(classe_membros = 0) AS nao_fizeram
            FROM membros;
        """)
        classe = fetch_one_dict(cursor)

        # CONSAGRAÇÃO
        cursor.execute("""
            SELECT
                SUM(consagracao = 1) AS consagrados,
                SUM(consagracao = 0) AS nao_consagrados
            FROM membros;
        """)
        consagracao = fetch_one_dict(cursor)

        # EVOLUÇÃO MENSAL
        cursor.execute("""
            SELECT
                DATE_FORMAT(data_cadastro, '%Y-%m') AS mes,
                COUNT(*) AS total
            FROM membros
            GROUP BY mes
            ORDER BY mes;
        """)
        mensal = fetch_all_dict(cursor)

        # CIDADES
        cursor.execute("""
            SELECT
                COALESCE(cidade, 'Não informada') AS cidade,
                COUNT(*) AS total
            FROM membros
            GROUP BY cidade
            ORDER BY total DESC
            LIMIT 10;
        """)
        cidades = fetch_all_dict(cursor)

        cursor.close()
        conn.close()

        return jsonify({
            "total": total,
            "genero": genero,
            "estado_civil": estado_civil,
            "novo_comeco": novo_comeco,
            "classe": classe,
            "consagracao": consagracao,
            "mensal": mensal,
            "cidades": cidades
        }), 200

    except Exception as e:
        logging.exception(e)
        return jsonify({"error": str(e)}), 500

# ============================================================
# REGISTRO
# ============================================================
def register(app):
    app.register_blueprint(bp_membros)
