from flask import Blueprint, request, jsonify, render_template
from database import get_db_connection
from contextlib import closing

bp_agenda = Blueprint("agendamentos", __name__)

def register(app):
    app.register_blueprint(bp_agenda)


# ============================================
# PÁGINA PÚBLICA
# ============================================
@bp_agenda.route("/agendar")
def pagina_agendar():
    return render_template("agendar_espacos.html")


# ============================================
# API — LISTAR ESPAÇOS
# ============================================
@bp_agenda.route("/api/espacos/listar")
def listar_espacos():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome FROM spaces ORDER BY nome")
            espacos = cursor.fetchall()

        return jsonify({"espacos": espacos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# API — LISTAR RESERVAS DE UM ESPAÇO
# ============================================
@bp_agenda.route("/api/reservas/listar/<int:space_id>/<data>")
def listar_reservas(space_id, data):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id,
                       TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                       TIME_FORMAT(hora_fim, '%H:%i')    AS hora_fim,
                       finalidade,
                       nome
                FROM reservas
                WHERE space_id = %s AND data = %s
                ORDER BY hora_inicio
            """, (space_id, data))

            reservas = cursor.fetchall()

        return jsonify({"reservas": reservas})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# API — NOVA RESERVA (COM VALIDAÇÃO)
# ============================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    data_json = request.json

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # ===============================
            # VERIFICAR CONFLITO DE HORÁRIO
            # ===============================
            cursor.execute("""
                SELECT id
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                  AND (%s < hora_fim AND %s > hora_inicio)
            """, (
                data_json["space_id"],
                data_json["data"],
                data_json["hora_inicio"],
                data_json["hora_fim"]
            ))

            conflito = cursor.fetchone()

            if conflito:
                return jsonify({
                    "status": "error",
                    "message": "⚠ Este espaço já está reservado neste horário!"
                }), 409

            # ===============================
            # INSERIR RESERVA
            # ===============================
            sql = """
                INSERT INTO reservas
                    (space_id, nome, telefone, finalidade, data,
                     hora_inicio, hora_fim, criado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """

            cursor.execute(sql, (
                data_json["space_id"],
                data_json["nome"],
                data_json["telefone"],
                data_json["finalidade"],
                data_json["data"],
                data_json["hora_inicio"],
                data_json["hora_fim"]
            ))

            conn.commit()

        # Resumo para exibir na tela:
        resumo = {
            "espaco_id": data_json["space_id"],
            "nome": data_json["nome"],
            "data": data_json["data"],
            "hora_inicio": data_json["hora_inicio"],
            "hora_fim": data_json["hora_fim"],
            "finalidade": data_json["finalidade"]
        }

        return jsonify({
            "status": "success",
            "message": "Reserva registrada com sucesso!",
            "resumo": resumo
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================
# ADMIN — LISTAR TODAS AS RESERVAS
# ============================================
@bp_agenda.route("/admin/reservas")
def admin_reservas():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT r.id,
                       r.data,
                       TIME_FORMAT(r.hora_inicio, '%H:%i') AS hora_inicio,
                       TIME_FORMAT(r.hora_fim, '%H:%i')   AS hora_fim,
                       r.nome,
                       r.finalidade,
                       s.nome AS espaco
                FROM reservas r
                JOIN spaces s ON s.id = r.space_id
                ORDER BY r.data DESC, r.hora_inicio
            """)

            reservas = cursor.fetchall()

        return render_template("admin_reservas.html", reservas=reservas)

    except Exception as e:
        return f"Erro: {e}", 500


# ============================================
# ADMIN — EXCLUIR RESERVA
# ============================================
@bp_agenda.route("/admin/reservas/excluir/<int:id>", methods=["POST"])
def excluir_reserva(id):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM reservas WHERE id = %s", (id,))
            conn.commit()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
