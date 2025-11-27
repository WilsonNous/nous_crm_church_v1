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
# API — LISTAR RESERVAS POR ESPAÇO + DIA
# ============================================
@bp_agenda.route("/api/reservas/listar/<int:space_id>/<data>")
def listar_reservas(space_id, data):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id,
                       time_format(hora_inicio, '%H:%i') AS hora_inicio,
                       time_format(hora_fim, '%H:%i') AS hora_fim,
                       finalidade, nome, status
                FROM reservas
                WHERE space_id = %s AND data = %s
                ORDER BY hora_inicio
            """, (space_id, data))

            reservas = cursor.fetchall()

        return jsonify({"reservas": reservas})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# API — NOVA RESERVA (com bloqueio e status pendente)
# ============================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    dados = request.json

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Verificar conflito de horário
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                  AND status != 'negado'
                  AND (
                        (hora_inicio <= %s AND hora_fim > %s) OR
                        (hora_inicio < %s AND hora_fim >= %s) OR
                        (%s <= hora_inicio AND %s > hora_inicio)
                  )
            """, (
                dados["space_id"],
                dados["data"],
                dados["hora_inicio"], dados["hora_inicio"],
                dados["hora_fim"], dados["hora_fim"],
                dados["hora_inicio"], dados["hora_fim"]
            ))

            conflito = cursor.fetchone()["total"]

            if conflito > 0:
                return jsonify({
                    "status": "error",
                    "message": "Já existe uma reserva neste horário. Aguarde aprovação ou escolha outro horário."
                }), 409

            # Inserir como pendente
            sql = """
                INSERT INTO reservas (
                    space_id, nome, telefone, finalidade,
                    data, hora_inicio, hora_fim,
                    status, criado_em
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'pendente',NOW())
            """

            cursor.execute(sql, (
                dados["space_id"],
                dados["nome"],
                dados["telefone"],
                dados["finalidade"],
                dados["data"],
                dados["hora_inicio"],
                dados["hora_fim"]
            ))

            conn.commit()

        return jsonify({
            "status": "success",
            "message": "Reserva registrada! Ela ficará PENDENTE até aprovação da Secretaria."
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
                SELECT r.id, r.data,
                       time_format(r.hora_inicio, '%H:%i') AS hora_inicio,
                       time_format(r.hora_fim, '%H:%i') AS hora_fim,
                       r.nome, r.finalidade, r.status,
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
# ADMIN — ALTERAR STATUS (aprovar/negar)
# ============================================
@bp_agenda.route("/admin/reservas/alterar/<int:id>/<acao>", methods=["POST"])
def alterar_status(id, acao):
    if acao not in ["aprovar", "negar"]:
        return jsonify({"error": "Ação inválida"}), 400

    novo_status = "aprovado" if acao == "aprovar" else "negado"

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE reservas
                SET status = %s
                WHERE id = %s
            """, (novo_status, id))

            conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
