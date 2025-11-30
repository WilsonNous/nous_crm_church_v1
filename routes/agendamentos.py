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
