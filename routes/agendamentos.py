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
                       time_format(hora_inicio, '%%H:%%i') AS hora_inicio,
                       time_format(hora_fim, '%%H:%%i') AS hora_fim,
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
# API — NOVA RESERVA (com bloqueio + mostrar conflito)
# ============================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    dados = request.json

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Procurar conflito
            cursor.execute("""
                SELECT 
                    id,
                    time_format(hora_inicio, '%%H:%%i') AS hora_inicio,
                    time_format(hora_fim, '%%H:%%i') AS hora_fim,
                    nome,
                    finalidade,
                    status
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                  AND status != 'negado'
                  AND (
                        (hora_inicio <= %s AND hora_fim > %s) OR
                        (hora_inicio < %s AND hora_fim >= %s) OR
                        (%s <= hora_inicio AND %s > hora_inicio)
                  )
                LIMIT 1
            """, (
                dados["space_id"],
                dados["data"],
                dados["hora_inicio"], dados["hora_inicio"],
                dados["hora_fim"], dados["hora_fim"],
                dados["hora_inicio"], dados["hora_fim"]
            ))

            conflito = cursor.fetchone()

            if conflito:
                return jsonify({
                    "status": "error",
                    "message": "Já existe uma reserva neste horário.",
                    "conflito": {
                        "inicio": conflito["hora_inicio"],
                        "fim": conflito["hora_fim"],
                        "responsavel": conflito["nome"],
                        "finalidade": conflito["finalidade"],
                        "status": conflito["status"]
                    }
                }), 409

            # Inserir reserva pendente
            cursor.execute("""
                INSERT INTO reservas (
                    space_id, nome, telefone, finalidade,
                    data, hora_inicio, hora_fim,
                    status, criado_em
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,'pendente',NOW())
            """, (
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
                cursor = conn.cursor(dictionary=True)
            
                cursor.execute("""
                    SELECT r.id, r.data,
                           time_format(r.hora_inicio, '%%H:%%i') AS hora_inicio,
                           time_format(r.hora_fim, '%%H:%%i') AS hora_fim,
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
# ADMIN — ALTERAR STATUS
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
