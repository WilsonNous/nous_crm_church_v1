import logging, os, requests
from flask import request, jsonify
from database import salvar_envio_evento, listar_envios_eventos, filtrar_visitantes_para_evento, get_db_connection

def register(app):
    @app.route('/api/eventos/filtrar', methods=['POST'])
    def api_eventos_filtrar():
        try:
            data = request.json
            visitantes = filtrar_visitantes_para_evento(
                data_inicio=data.get("data_inicio"),
                data_fim=data.get("data_fim"),
                idade_min=data.get("idade_min"),
                idade_max=data.get("idade_max"),
                genero=data.get("genero")
            )
            return jsonify({"status": "success", "visitantes": visitantes}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/filtrar: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

