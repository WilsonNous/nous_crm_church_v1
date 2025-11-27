from flask import Blueprint, request, jsonify, render_template
from models import db, Space, Reserva

bp_agenda = Blueprint("agendamentos", __name__)

def register(app):
    app.register_blueprint(bp_agenda)


# ============================
#  PÁGINA PÚBLICA
# ============================
@bp_agenda.route("/agendar")
def pagina_agendar():
    return render_template("agendar_espacos.html")


# ============================
#  API — LISTAR ESPAÇOS
# ============================
@bp_agenda.route("/api/espacos/listar")
def listar_espacos():
    espacos = Space.query.all()
    return jsonify({"espacos": [
        {"id": e.id, "nome": e.nome} for e in espacos
    ]})


# ============================
#  API — LISTAR RESERVAS
# ============================
@bp_agenda.route("/api/reservas/listar/<int:space_id>/<data>")
def listar_reservas(space_id, data):
    reservas = Reserva.query.filter_by(space_id=space_id, data=data).all()
    return jsonify({"reservas": [
        {
            "id": r.id,
            "hora_inicio": r.hora_inicio.strftime("%H:%M"),
            "hora_fim": r.hora_fim.strftime("%H:%M"),
            "finalidade": r.finalidade,
            "nome": r.nome
        }
        for r in reservas
    ]})


# ============================
#  API — NOVA RESERVA
# ============================
@bp_agenda.route("/api/reservas/nova", methods=["POST"])
def nova_reserva():
    data = request.json

    reserva = Reserva(
        space_id=data["space_id"],
        nome=data["nome"],
        telefone=data["telefone"],
        finalidade=data["finalidade"],
        data=data["data"],
        hora_inicio=data["hora_inicio"],
        hora_fim=data["hora_fim"]
    )

    db.session.add(reserva)
    db.session.commit()

    return jsonify({"status": "success", "message": "Reserva registrada com sucesso!"})


# ============================
#  ADMIN — LISTAGEM
# ============================
@bp_agenda.route("/admin/reservas")
def admin_reservas():
    reservas = Reserva.query.order_by(Reserva.data.desc()).all()
    return render_template("admin_reservas.html", reservas=reservas)


# ============================
#  ADMIN — EXCLUIR
# ============================
@bp_agenda.route("/admin/reservas/excluir/<int:id>", methods=["POST"])
def excluir_reserva(id):
    reserva = Reserva.query.get(id)
    if not reserva:
        return jsonify({"error": "Reserva não encontrada"})

    db.session.delete(reserva)
    db.session.commit()

    return jsonify({"success": True})
