import logging
import os
import requests
from flask import request, jsonify, Response
from database import (
    salvar_visitante, visitante_existe, normalizar_para_recebimento,
    listar_todos_visitantes, monitorar_status_visitantes,
    visitantes_listar_fases, visitantes_listar_estatisticas,
    salvar_conversa, obter_conversa_por_visitante, get_db_connection   
)

def register(app):
    @app.route('/api/register', methods=['POST'])
    def register_visitante():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Nenhum dado enviado."}), 400

        telefone = normalizar_para_recebimento(data.get('phone'))
        if visitante_existe(telefone):
            return jsonify({"error": "Visitante já cadastrado."}), 400

        visitante_data = {
            'nome': data.get('name'),
            'telefone': telefone,
            'email': data.get('email'),
            'data_nascimento': data.get('birthdate'),
            'cidade': data.get('city'),
            'genero': data.get('gender'),
            'estado_civil': data.get('maritalStatus'),
            'igreja_atual': data.get('currentChurch'),
            'frequenta_igreja': 1 if str(data.get('attendingChurch')).lower() == 'true' else 0,
            'indicacao': data.get('referral'),
            'membro': data.get('membership'),
            'pedido_oracao': data.get('prayerRequest'),
            'horario_contato': data.get('contactTime')
        }
        try:
            if salvar_visitante(**visitante_data):
                return jsonify({"message": "Cadastro realizado com sucesso!"}), 201
            else:
                return jsonify({"error": "Erro ao cadastrar visitante."}), 500
        except Exception as e:
            logging.exception(f"Erro ao salvar visitante: {e}")
            return jsonify({"error": "Erro interno do servidor"}), 500

    @app.route('/api/get-visitors', methods=['GET'])
    def api_get_visitors():
        try:
            visitantes = listar_todos_visitantes()
            visitors = []
            for v in visitantes:
                if isinstance(v, dict):
                    visitors.append({
                        "id": v.get("id"),
                        "name": v.get("nome"),
                        "phone": v.get("telefone")
                    })
                else:
                    visitors.append({
                        "id": v[0],
                        "name": v[1],
                        "phone": v[2] if len(v) > 2 else None
                    })
            return jsonify({"status": "success", "visitors": visitors}), 200
        except Exception as e:
            logging.error(f"Erro em /api/get-visitors: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/monitor-status', methods=['GET'])
    def monitor_status():
        try:
            status_info = monitorar_status_visitantes()
            return jsonify(status_info), 200 if status_info else 500
        except Exception as e:
            logging.error(f"Erro ao monitorar status: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/fases-visitantes', methods=['GET'])
    def get_fases_visitantes():
        try:
            return jsonify(visitantes_listar_fases()), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/estatisticas-visitantes', methods=['GET'])
    def get_estatisticas_visitantes():
        try:
            return jsonify(visitantes_listar_estatisticas()), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ==============================
    # NOVO: Envio manual via Z-API
    # ==============================
    @app.route('/api/send-message-manual', methods=['POST'])
    def api_send_message_manual():
        try:
            data = request.get_json()
            numero = data.get("numero")
            mensagem = data.get("mensagem", "")
            imagem_url = data.get("imagem_url")

            if not numero:
                return jsonify({"success": False, "error": "Número não informado"}), 400

            ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
            ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
            ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")
            if not (ZAPI_INSTANCE and ZAPI_TOKEN and ZAPI_CLIENT_TOKEN):
                return jsonify({"success": False, "error": "Configuração Z-API ausente"}), 500

            headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}
            telefone_envio = f"55{numero}" if not numero.startswith("55") else numero

            if imagem_url:
                payload = {"phone": telefone_envio, "caption": mensagem, "image": imagem_url}
                url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
            else:
                payload = {"phone": telefone_envio, "message": mensagem}
                url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.ok:
                logging.info(f"✅ Mensagem enviada via Z-API para {telefone_envio}")
                salvar_conversa(telefone_envio, mensagem, tipo="enviada", origem="integra+")
                return jsonify({"success": True}), 200
            else:
                return jsonify({"success": False, "error": f"Falha: {response.status_code}"}), 500
        except Exception as e:
            logging.error(f"Erro em /api/send-message-manual: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/visitantes/fase-null', methods=['GET'])
    def get_visitantes_fase_null():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.nome, v.telefone
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                WHERE s.fase_id IS NULL
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify({"status": "success", "visitantes": rows}), 200
        except Exception as e:
            logging.error(f"Erro em /api/visitantes/fase-null: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500


    # ==============================
    # Conversas do Visitante (histórico em HTML)
    # ==============================
    @app.route('/api/conversas/<int:visitante_id>', methods=['GET'])
    def api_get_conversas(visitante_id):
        try:
            html = obter_conversa_por_visitante(visitante_id)

            # estilo inline simples para chat
            styled_html = f"""
            <html>
            <head>
              <meta charset="utf-8">
              <title>Histórico de Conversas</title>
              <style>
                body {{
                  font-family: Arial, sans-serif;
                  background: #f4f4f9;
                  padding: 20px;
                }}
                .chat-conversa {{
                  max-width: 600px;
                  margin: auto;
                  background: #fff;
                  border-radius: 10px;
                  padding: 15px;
                  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
                }}
                .chat-conversa p {{
                  padding: 8px 12px;
                  border-radius: 8px;
                  margin: 8px 0;
                }}
                .chat-conversa p strong {{
                  display: block;
                  font-size: 0.9em;
                  margin-bottom: 4px;
                }}
                .chat-conversa p small {{
                  display: block;
                  font-size: 0.7em;
                  color: #888;
                  margin-top: 4px;
                }}
                .chat-conversa p.bot {{
                  background: #e0f7fa;
                  text-align: left;
                }}
                .chat-conversa p.user {{
                  background: #e8eaf6;
                  text-align: right;
                }}
              </style>
            </head>
            <body>
              <h2>💬 Conversas do Visitante #{visitante_id}</h2>
              {html}
            </body>
            </html>
            """

            return Response(styled_html, mimetype='text/html')
        except Exception as e:
            logging.error(f"Erro em /api/conversas/{visitante_id}: {e}")
            return Response(f"<p>Erro: {e}</p>", mimetype='text/html', status=500)
