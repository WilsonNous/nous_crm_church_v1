import logging
import os
from flask import request, jsonify, Response

from database import (
    salvar_visitante, visitante_existe, normalizar_para_recebimento,
    listar_todos_visitantes, monitorar_status_visitantes,
    visitantes_listar_fases, visitantes_listar_estatisticas,
    salvar_conversa, obter_conversa_por_visitante, get_db_connection, atualizar_status
)

# ✅ usa fila unificada (com callback)
from servicos.fila_mensagens import adicionar_na_fila


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
    # ✅ Envio manual (PADRÃO FILA + CONFIRMAÇÃO PERSISTENTE)
    # ==============================
    @app.route('/api/send-message-manual', methods=['POST'])
    def api_send_message_manual():
        try:
            data = request.get_json() or {}

            visitante_id = data.get("visitante_id")  # opcional
            numero = (data.get("numero") or "").strip()
            mensagem = (data.get("mensagem") or "").strip()
            imagem_url = data.get("imagem_url")  # opcional

            if not numero:
                return jsonify({"success": False, "error": "Número não informado"}), 400
            if not mensagem:
                return jsonify({"success": False, "error": "Mensagem vazia"}), 400

            # 🔧 Normaliza para formato Z-API (55 + DDD + 9 + número = 13 dígitos)
            telefone_zapi = f"55{numero}" if not str(numero).startswith("55") else str(numero)
            
            # 🔧 Normaliza para formato do banco (DDD + 9 + número = 11 dígitos, sem 55)
            telefone_db = normalizar_para_recebimento(telefone_zapi)

            # ✅ Meta com tipo="manual" para gatilho no worker
            meta = {
                "origem": "integra+",
                "tipo": "manual",
                "visitante_id": visitante_id,
                "telefone_raw": telefone_db,  # Formato do banco para busca
                "telefone_zapi": telefone_zapi  # Formato para envio
            }

            # 📤 Enfileira SEM callbacks críticos (lógica vai para o worker persistente)
            ok_fila = adicionar_na_fila(
                telefone_zapi,  # Número no formato Z-API
                mensagem,
                imagem_url=imagem_url,
                # on_success e on_fail REMOVIDOS para status crítico
                meta=meta
            )

            if not ok_fila:
                return jsonify({"success": False, "error": "Falha ao enfileirar mensagem"}), 500

            logging.info(f"✅ Mensagem manual enfileirada | tel_db={telefone_db} | tel_zapi={telefone_zapi}")
            
            return jsonify({
                "success": True,
                "message": "Mensagem enfileirada. Status será atualizado após confirmação."
            }), 200

        except Exception as e:
            logging.exception(f"❌ Erro em /api/send-message-manual: {e}")
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
                WHERE s.fase_id IS NULL OR s.fase_id = ''
            """)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            visitantes = []
            for row in rows:
                if isinstance(row, dict):
                    visitantes.append({
                        "id": row.get("id"),
                        "nome": row.get("nome"),
                        "telefone": row.get("telefone")
                    })
                else:
                    visitantes.append({
                        "id": row[0],
                        "nome": row[1],
                        "telefone": row[2] if len(row) > 2 else None
                    })

            logging.info(f"🔍 Visitantes com fase nula: {len(visitantes)} encontrados")
            return jsonify({"status": "success", "visitantes": visitantes}), 200

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
