import logging
from flask import Blueprint, jsonify, request, render_template
from flask_jwt_extended import jwt_required

from servicos.planejador_boas_vindas import get_status, set_enabled, executar_uma_vez, iniciar_planejador

bp = Blueprint("planejador_boas_vindas", __name__)


def register(app):
    app.register_blueprint(bp)
    try:
        iniciar_planejador()
    except Exception:
        logging.exception("Falha ao iniciar planejador de boas-vindas")


@bp.route('/app/planejador-boas-vindas')
def page():
    return render_template('planejador_boas_vindas.html')


@bp.route('/api/planejador-boas-vindas/status', methods=['GET'])
@jwt_required()
def status():
    try:
        return jsonify({"status": "success", "planner": get_status()}), 200
    except Exception as exc:
        logging.exception("Erro ao consultar planejador")
        return jsonify({"status": "error", "message": str(exc)}), 500


@bp.route('/api/planejador-boas-vindas/toggle', methods=['POST'])
@jwt_required()
def toggle():
    try:
        data = request.get_json() or {}
        if "enabled" not in data:
            return jsonify({"status": "error", "message": "Campo enabled obrigatório"}), 400
        planner = set_enabled(bool(data.get("enabled")))
        return jsonify({"status": "success", "planner": planner}), 200
    except Exception as exc:
        logging.exception("Erro ao alterar planejador")
        return jsonify({"status": "error", "message": str(exc)}), 500


@bp.route('/api/planejador-boas-vindas/run', methods=['POST'])
@jwt_required()
def run_now():
    try:
        result = executar_uma_vez(force=False)
        return jsonify({"status": "success", "result": result, "planner": get_status()}), 200
    except Exception as exc:
        logging.exception("Erro na execução do planejador")
        return jsonify({"status": "error", "message": str(exc)}), 500
