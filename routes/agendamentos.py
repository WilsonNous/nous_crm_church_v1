from flask import Blueprint, request, jsonify, render_template
from database import get_db_connection
from contextlib import closing
from datetime import datetime, timedelta

# 🔗 Z-API
from servicos.zapi_cliente import enviar_mensagem

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
        with closing(get_db_connection()) as conn:
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
        # valida a data para evitar 500
        try:
            datetime.strptime(data, "%Y-%m-%d")
        except:
            return jsonify({"reservas": []})

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
                WHERE space_id = %s AND data = %s
                ORDER BY hora_inicio
            """, (space_id, data))

            reservas = cursor.fetchall()
        return jsonify({"reservas": reservas})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# API — Nova reserva (com regras de conflito atualizadas)
# ============================================================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    dados = request.json

    try:
        # normalizar horários
        data_res = datetime.strptime(dados["data"], "%Y-%m-%d")
        h_inicio = datetime.strptime(dados["hora_inicio"], "%H:%M")
        h_fim = datetime.strptime(dados["hora_fim"], "%H:%M")

        # atravessar madrugada
        if h_fim <= h_inicio:
            h_fim = h_fim + timedelta(days=1)

        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # ====================================================
            # 1) VERIFICAR conflito com APROVADAS (bloqueio total)
            # ====================================================
            cursor.execute("""
                SELECT 
                    id,
                    TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                    TIME_FORMAT(hora_fim,   '%H:%i') AS hora_fim,
                    nome,
                    finalidade
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                  AND status = 'aprovado'
                  AND (
                        (hora_inicio <= %s AND hora_fim > %s) OR
                        (hora_inicio < %s AND hora_fim >= %s) OR
                        (%s <= hora_inicio AND %s > hora_inicio)
                  )
            """, (
                dados["space_id"], dados["data"],
                dados["hora_inicio"], dados["hora_inicio"],
                dados["hora_fim"],   dados["hora_fim"],
                dados["hora_inicio"], dados["hora_fim"],
            ))

            conflito_aprovado = cursor.fetchall()
            if conflito_aprovado:
                c = conflito_aprovado[0]
                return jsonify({
                    "status": "error",
                    "message": "Este horário já possui uma reserva *aprovada*.",
                    "conflito": {
                        "inicio": c["hora_inicio"],
                        "fim": c["hora_fim"],
                        "responsavel": c["nome"],
                        "finalidade": c["finalidade"],
                    },
                }), 409

            # ====================================================
            # 2) CONTAR pendentes (limite = 3)
            # ====================================================
            cursor.execute("""
                SELECT COUNT(*) AS qtd
                FROM reservas
                WHERE space_id = %s
                  AND data = %s
                  AND status = 'pendente'
                  AND (
                        (hora_inicio <= %s AND hora_fim > %s) OR
                        (hora_inicio < %s AND hora_fim >= %s) OR
                        (%s <= hora_inicio AND %s > hora_inicio)
                  )
            """, (
                dados["space_id"], dados["data"],
                dados["hora_inicio"], dados["hora_inicio"],
                dados["hora_fim"],   dados["hora_fim"],
                dados["hora_inicio"], dados["hora_fim"],
            ))

            qtd_pendentes = cursor.fetchone()["qtd"]

            if qtd_pendentes >= 3:
                return jsonify({
                    "status": "error",
                    "message": "Limite de 3 reservas pendentes neste horário."
                }), 409

            # ====================================================
            # 3) INSERIR reserva pendente
            # ====================================================
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
            "message": "Reserva registrada como PENDENTE. A Secretaria irá analisar."
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# ============================================================
# ADMIN — Listar Reservas
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
        with closing(get_db_connection()) as conn:
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

    if acao not in ["aprovar", "negar"]:
        return jsonify({"error": "Ação inválida"}), 400

    novo_status = "aprovado" if acao == "aprovar" else "negado"

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT nome, telefone, data,
                       TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                       TIME_FORMAT(hora_fim, '%H:%i') AS hora_fim
                FROM reservas WHERE id = %s
            """, (id,))
            r = cursor.fetchone()

            cursor.execute("""
                UPDATE reservas SET status = %s WHERE id = %s
            """, (novo_status, id))

            conn.commit()

        mensagem = (
            f"Olá {r['nome']}! Sua solicitação de uso do espaço em {r['data']} "
            f"das {r['hora_inicio']} às {r['hora_fim']} foi *{novo_status.upper()}*."
        )

        enviar_mensagem(r["telefone"], mensagem)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ============================================================
# ADMIN — Excluir (com WhatsApp)
# ============================================================
@bp_agenda.route("/admin/reservas/excluir/<int:id>", methods=["POST"])
def excluir_reserva(id):

    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT nome, telefone, data,
                       TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
                       TIME_FORMAT(hora_fim, '%H:%i') AS hora_fim
                FROM reservas WHERE id = %s
            """, (id,))
            r = cursor.fetchone()

            cursor.execute("DELETE FROM reservas WHERE id = %s", (id,))
            conn.commit()

        mensagem = (
            f"Olá {r['nome']}! Sua solicitação de uso do espaço no dia {r['data']} "
            f"das {r['hora_inicio']} às {r['hora_fim']} foi *EXCLUÍDA* pela Secretaria."
        )

        enviar_mensagem(r["telefone"], mensagem)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
