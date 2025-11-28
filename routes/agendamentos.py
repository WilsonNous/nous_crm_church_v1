from flask import Blueprint, request, jsonify, render_template
from database import get_db_connection
from contextlib import closing
import requests
import os

bp_agenda = Blueprint("agendamentos", __name__)

def register(app):
    app.register_blueprint(bp_agenda)

# ============================================================
# Função auxiliar — enviar WhatsApp via Z-API
# ============================================================
def enviar_whatsapp(numero, mensagem):
    try:
        url = os.getenv("ZAPI_URL")
        token = os.getenv("ZAPI_TOKEN")

        if not url or not token:
            return False

        payload = {
            "phone": numero,
            "message": mensagem
        }

        r = requests.post(
            f"{url}/send-message",
            json=payload,
            headers={"Authorization": token},
            timeout=10
        )
        return r.status_code == 200

    except Exception:
        return False


# ============================================================
# Página pública — formulário de agendamento
# ============================================================
@bp_agenda.route("/agendar")
def pagina_agendar():
    return render_template("agendar_espacos.html")


# ============================================================
# API — listar espaços
# ============================================================
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


# ============================================================
# API — listar reservas por dia/espaço
# ============================================================
@bp_agenda.route("/api/reservas/listar/<int:space_id>/<data>")
def listar_reservas(space_id, data):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    id,
                    TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(hora_fim,   '%H:%i') AS hora_fim,
                    finalidade,
                    nome,
                    status
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                ORDER BY hora_inicio
            """, (space_id, data))

            reservas = cursor.fetchall()
        return jsonify({"reservas": reservas})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API — inserir nova reserva com bloqueio
# ============================================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    dados = request.json

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Verifica conflito
            cursor.execute("""
                SELECT 
                    id,
                    TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(hora_fim,   '%H:%i') AS hora_fim,
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
                dados["hora_fim"],   dados["hora_fim"],
                dados["hora_inicio"], dados["hora_fim"],
            ))

            conflito = cursor.fetchall()

            if conflito:
                c = conflito[0]
                return jsonify({
                    "status": "error",
                    "message": "Já existe uma reserva neste horário.",
                    "conflito": {
                        "inicio": c["hora_inicio"],
                        "fim": c["hora_fim"],
                        "responsavel": c["nome"],
                        "finalidade": c["finalidade"],
                        "status": c["status"]
                    }
                }), 409

            # Insere reserva
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
                dados["hora_fim"],
            ))

            conn.commit()

        return jsonify({
            "status": "success",
            "message": "Reserva registrada! Ela ficará PENDENTE até aprovação."
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================================
# ADMIN — listar reservas
# ============================================================
@bp_agenda.route("/admin/reservas")
def admin_reservas():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    r.id,
                    r.data,
                    TIME_FORMAT(r.hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(r.hora_fim,   '%H:%i') AS hora_fim,
                    r.nome,
                    r.finalidade,
                    r.telefone,
                    r.status,
                    s.nome AS espaco
                FROM reservas r
                JOIN spaces s ON s.id = r.space_id
                ORDER BY r.data DESC, r.hora_inicio
            """)

            reservas = cursor.fetchall()

        return render_template("admin_reservas.html", reservas=reservas)

    except Exception as e:
        return f"Erro no admin_reservas: {e}", 500


# ============================================================
# ADMIN — agenda geral
# ============================================================
@bp_agenda.route("/admin/agenda-geral")
def agenda_geral():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    r.id,
                    r.data,
                    TIME_FORMAT(r.hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(r.hora_fim,   '%H:%i') AS hora_fim,
                    r.nome,
                    r.finalidade,
                    r.telefone,
                    r.status,
                    s.nome AS espaco
                FROM reservas r
                JOIN spaces s ON s.id = r.space_id
                ORDER BY r.data ASC, r.hora_inicio ASC
            """)

            reservas = cursor.fetchall()

        return render_template("agenda_geral.html", reservas=reservas)

    except Exception as e:
        return f"Erro ao carregar agenda geral: {e}", 500



# ============================================================
# ADMIN — aprovar / negar
# ============================================================
@bp_agenda.route("/admin/reservas/alterar/<int:id>/<acao>", methods=["POST"])
def alterar_status(id, acao):

    if acao not in ["aprovar", "negar"]:
        return jsonify({"error": "Ação inválida"}), 400

    novo_status = "aprovado" if acao == "aprovar" else "negado"

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # pega info da reserva
            cursor.execute("SELECT nome, telefone, data, hora_inicio, hora_fim FROM reservas WHERE id = %s", (id,))
            r = cursor.fetchone()

            cursor.execute("""
                UPDATE reservas
                SET status = %s
                WHERE id = %s
            """, (novo_status, id))

            conn.commit()

        # MENSAGEM WHATSAPP
        msg = (
            f"Olá {r['nome']}, sua solicitação de uso de espaço no dia {r['data']} "
            f"das {r['hora_inicio']} às {r['hora_fim']} foi *{novo_status.upper()}*."
        )

        enviar_whatsapp(r["telefone"], msg)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# ADMIN — excluir
# ============================================================
@bp_agenda.route("/admin/reservas/excluir/<int:id>", methods=["POST"])
def excluir_reserva(id):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT nome, telefone, data, hora_inicio, hora_fim FROM reservas WHERE id = %s", (id,))
            r = cursor.fetchone()

            cursor.execute("DELETE FROM reservas WHERE id = %s", (id,))
            conn.commit()

        enviar_whatsapp(
            r["telefone"],
            f"Olá {r['nome']}, sua solicitação para {r['data']} "
            f"das {r['hora_inicio']} às {r['hora_fim']} foi *EXCLUÍDA* pela Secretaria."
        )

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
