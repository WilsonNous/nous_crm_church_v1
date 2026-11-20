from flask import Blueprint, request, jsonify, render_template
from database import get_db_connection
from contextlib import closing
from datetime import datetime, date
import logging

# 🔗 Z-API
from servicos.zapi_cliente import enviar_mensagem

def conexao_agenda():
    """Falha explícita se a conexão não estiver disponível.

    database.get_db_connection() registra o erro original e retorna None.
    """
    conn = get_db_connection()
    if conn is None:
        logging.error("Agenda: conexão MySQL indisponível; confira o erro anterior do database nos logs.")
        raise RuntimeError("Conexão com o banco de dados indisponível.")
    return conn


bp_agenda = Blueprint("agendamentos", __name__)

def register(app):
    app.register_blueprint(bp_agenda)


# ============================================================
# Página Pública
# ============================================================
@bp_agenda.route("/agendar")
def pagina_agendar():
    return render_template("agendar_espacos.html")


# ============================================================
# API — Listar espaços
# ============================================================
@bp_agenda.route("/api/espacos/listar")
def listar_espacos():
    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome FROM spaces ORDER BY nome")
            espacos = cursor.fetchall()
        return jsonify({"espacos": espacos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API — listar reservas por espaço e dia
# ============================================================
@bp_agenda.route("/api/reservas/listar/<int:space_id>/<data>")
def listar_reservas(space_id, data):
    try:
        try:
            date.fromisoformat(data)
        except ValueError:
            return jsonify({"error": "Data inválida."}), 400

        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    TIME_FORMAT(hora_inicio, '%%H:%%i') AS hora_inicio,
                    TIME_FORMAT(hora_fim, '%%H:%%i') AS hora_fim,
                    status
                FROM reservas
                WHERE space_id = %s AND data = %s
                  AND status IN ('pendente', 'aprovado')
                ORDER BY hora_inicio
            """, (space_id, data))
            reservas = cursor.fetchall()
        return jsonify({"reservas": reservas})
    except Exception:
        logging.exception("Falha ao consultar disponibilidade de espaço")
        return jsonify({"error": "Não foi possível consultar a agenda."}), 500


# ============================================================
# API — Nova reserva
# ============================================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"status": "error", "message": "Envie os dados da reserva em JSON."}), 400

    try:
        space_id = int(dados.get("space_id"))
        data_res = date.fromisoformat(dados.get("data", ""))
        inicio = datetime.strptime(dados.get("hora_inicio", ""), "%H:%M").time()
        fim = datetime.strptime(dados.get("hora_fim", ""), "%H:%M").time()
        nome = str(dados.get("nome") or "").strip()
        telefone = str(dados.get("telefone") or "").strip()
        finalidade = str(dados.get("finalidade") or "").strip()
        if space_id <= 0 or not nome or not telefone or not finalidade:
            raise ValueError("Campos obrigatórios ausentes")
        if len(nome) > 150 or len(telefone) > 30 or len(finalidade) > 500:
            raise ValueError("Campos excedem o tamanho permitido")
        if data_res < date.today():
            return jsonify({"status": "error", "message": "Não é possível reservar uma data passada."}), 400
        if fim <= inicio:
            return jsonify({"status": "error", "message": "A hora final deve ser posterior à inicial. Reservas após a meia-noite devem ser divididas por dia."}), 400
    except (TypeError, ValueError, KeyError):
        return jsonify({"status": "error", "message": "Confira espaço, data, horários e campos obrigatórios."}), 400

    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()
            # Serializa operações por espaço para evitar reservas simultâneas conflitantes.
            cursor.execute("SELECT id FROM spaces WHERE id = %s FOR UPDATE", (space_id,))
            if not cursor.fetchone():
                return jsonify({"status": "error", "message": "Espaço não encontrado."}), 404

            cursor.execute("""
                SELECT COUNT(*) AS qtd FROM reservas
                WHERE space_id = %s AND data = %s AND status = 'aprovado'
                  AND hora_inicio < %s AND hora_fim > %s
            """, (space_id, data_res, fim, inicio))
            if cursor.fetchone()["qtd"]:
                return jsonify({"status": "error", "message": "Este horário já possui uma reserva aprovada."}), 409

            cursor.execute("""
                SELECT COUNT(*) AS qtd FROM reservas
                WHERE space_id = %s AND data = %s AND status = 'pendente'
                  AND hora_inicio < %s AND hora_fim > %s
            """, (space_id, data_res, fim, inicio))
            if cursor.fetchone()["qtd"] >= 3:
                return jsonify({"status": "error", "message": "Limite de 3 reservas pendentes neste horário."}), 409

            cursor.execute("""
                SELECT COUNT(*) AS qtd FROM reservas
                WHERE space_id = %s AND data = %s AND status IN ('pendente', 'aprovado')
                  AND nome = %s AND telefone = %s AND finalidade = %s
                  AND hora_inicio = %s AND hora_fim = %s
            """, (space_id, data_res, nome, telefone, finalidade, inicio, fim))
            if cursor.fetchone()["qtd"]:
                return jsonify({"status": "error", "message": "Esta reserva já foi registrada."}), 409

            cursor.execute("""
                INSERT INTO reservas (
                    space_id, nome, telefone, finalidade,
                    data, hora_inicio, hora_fim, status, criado_em
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'pendente',NOW())
            """, (space_id, nome, telefone, finalidade, data_res, inicio, fim))
            conn.commit()
        return jsonify({"status": "success", "message": "Reserva registrada como PENDENTE. A Secretaria irá analisar."})
    except Exception:
        logging.exception("Falha ao cadastrar reserva")
        return jsonify({"status": "error", "message": "Não foi possível salvar a reserva. Tente novamente."}), 500


# ============================================================
# ADMIN — Listar Reservas
# ============================================================
@bp_agenda.route("/admin/reservas")
def admin_reservas():
    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    r.id,
                    DATE_FORMAT(r.data, '%d/%m/%Y') AS data,
                    TIME_FORMAT(r.hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(r.hora_fim,   '%H:%i') AS hora_fim,
                    r.nome,
                    r.telefone,
                    r.finalidade,
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
# ADMIN — Agenda Geral
# ============================================================
@bp_agenda.route("/admin/agenda-geral")
def agenda_geral():
    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    r.id,
                    r.data,
                    TIME_FORMAT(r.hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(r.hora_fim,   '%H:%i') AS hora_fim,
                    r.nome,
                    r.telefone,
                    r.finalidade,
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
# ADMIN — Aprovar / Negar (com WhatsApp)
# ============================================================
@bp_agenda.route("/admin/reservas/alterar/<int:id>/<acao>", methods=["POST"])
def alterar_status(id, acao):
    if acao not in ("aprovar", "negar"):
        return jsonify({"error": "Ação inválida"}), 400

    novo_status = "aprovado" if acao == "aprovar" else "negado"
    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()
            # Primeiro localiza o espaço, depois o bloqueia na mesma ordem do cadastro.
            cursor.execute("SELECT space_id FROM reservas WHERE id = %s", (id,))
            alvo = cursor.fetchone()
            if not alvo:
                return jsonify({"error": "Reserva não encontrada."}), 404
            cursor.execute("SELECT id FROM spaces WHERE id = %s FOR UPDATE", (alvo["space_id"],))
            cursor.execute("""
                SELECT id, space_id, nome, telefone, data, status,
                       hora_inicio, hora_fim,
                       TIME_FORMAT(hora_inicio, '%%H:%%i') AS inicio_formatado,
                       TIME_FORMAT(hora_fim, '%%H:%%i') AS fim_formatado
                FROM reservas WHERE id = %s FOR UPDATE
            """, (id,))
            r = cursor.fetchone()
            if not r:
                return jsonify({"error": "Reserva não encontrada."}), 404
            if r["status"] == novo_status:
                return jsonify({"success": True, "warning": "Reserva já estava com esse status."}), 200
            if r["status"] != "pendente":
                return jsonify({"error": "Somente reservas pendentes podem mudar de status."}), 409

            if novo_status == "aprovado":
                cursor.execute("""
                    SELECT COUNT(*) AS qtd FROM reservas
                    WHERE id <> %s AND space_id = %s AND data = %s
                      AND status = 'aprovado'
                      AND hora_inicio < %s AND hora_fim > %s
                """, (id, r["space_id"], r["data"], r["hora_fim"], r["hora_inicio"]))
                if cursor.fetchone()["qtd"]:
                    return jsonify({"error": "Conflito: outro agendamento já foi aprovado para esse espaço e horário."}), 409

            cursor.execute("UPDATE reservas SET status = %s WHERE id = %s", (novo_status, id))
            conn.commit()

        mensagem = (
            f"Olá {r['nome']}! Sua solicitação de uso do espaço em {r['data']} "
            f"das {r['inicio_formatado']} às {r['fim_formatado']} foi *{novo_status.upper()}*."
        )
        try:
            envio = enviar_mensagem(r["telefone"], mensagem)
            if not envio or not envio.get("success"):
                logging.warning("Notificação de reserva não confirmada | reserva_id=%s", id)
                return jsonify({"success": True, "warning": "Status salvo, mas a notificação por WhatsApp não foi confirmada."}), 200
        except Exception:
            logging.exception("Falha na notificação de reserva | reserva_id=%s", id)
            return jsonify({"success": True, "warning": "Status salvo, mas ocorreu falha ao notificar por WhatsApp."}), 200
        return jsonify({"success": True})
    except Exception:
        logging.exception("Falha ao alterar status de reserva | reserva_id=%s", id)
        return jsonify({"error": "Não foi possível alterar a reserva."}), 500


# ============================================================
# ADMIN — Excluir (com WhatsApp)
# ============================================================
@bp_agenda.route("/admin/reservas/excluir/<int:id>", methods=["POST"])
def excluir_reserva(id):

    try:
        with closing(conexao_agenda()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT nome, telefone, data,
                       TIME_FORMAT(hora_inicio, '%%H:%%i') AS hora_inicio,
                       TIME_FORMAT(hora_fim, '%%H:%%i') AS hora_fim
                FROM reservas WHERE id = %s
            """, (id,))
            r = cursor.fetchone()
            if not r:
                return jsonify({"error": "Reserva não encontrada."}), 404

            cursor.execute("DELETE FROM reservas WHERE id = %s", (id,))
            conn.commit()

        mensagem = (
            f"Olá {r['nome']}! Sua solicitação de uso do espaço no dia {r['data']} "
            f"das {r['hora_inicio']} às {r['hora_fim']} foi *EXCLUÍDA* pela Secretaria."
        )

        try:
            envio = enviar_mensagem(r["telefone"], mensagem)
            if not envio or not envio.get("success"):
                logging.warning("Notificação de reserva não confirmada | reserva_id=%s", id)
                return jsonify({
                    "success": True,
                    "warning": "Alteração salva, mas a notificação por WhatsApp não foi confirmada."
                }), 200
        except Exception:
            logging.exception("Falha na notificação de reserva | reserva_id=%s", id)
            return jsonify({
                "success": True,
                "warning": "Alteração salva, mas ocorreu uma falha ao notificar pelo WhatsApp."
            }), 200

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
