# routes.py
import logging
import os
from datetime import datetime
import requests
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

# --- JWT compatibility shim ---
try:
    from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
except Exception:
    def create_access_token(identity):
        return f"MOCK_TOKEN_FOR_{identity}"
    def jwt_required(fn=None, *args, **kwargs):
        if fn is None:
            def wrapper(f): return f
            return wrapper
        return fn
    def get_jwt_identity(): return None
# End shim

from werkzeug.security import check_password_hash
import pandas as pd

from botmsg import processar_mensagem
from database import (
    salvar_visitante, visitante_existe, normalizar_para_recebimento,
    listar_todos_visitantes, monitorar_status_visitantes,
    visitantes_listar_fases, visitantes_listar_estatisticas,
    salvar_conversa, atualizar_status, obter_conversa_por_visitante,
    membro_existe, salvar_membro, obter_total_membros, obter_total_visitantes,
    obter_total_discipulados, obter_dados_genero, get_db_connection,
    salvar_envio_evento, listar_envios_eventos, filtrar_visitantes_para_evento
)

from twilio.rest import Client
from ia_integracao import IAIntegracao
ia_integracao = IAIntegracao()

# --- LOGIN (seguro com ENV) ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", None)  # deve estar já com generate_password_hash()
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")

def register_routes(app_instance: Flask) -> None:

    # --- LOGIN ---
    @app_instance.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json()
        if not data:
            return jsonify({'status': 'failed', 'message': 'Nenhum dado foi fornecido'}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'status': 'failed', 'message': 'Usuário e senha são obrigatórios'}), 400

        if username == ADMIN_USER:
            if ADMIN_PASSWORD_HASH:
                if not check_password_hash(ADMIN_PASSWORD_HASH, password):
                    return jsonify({'status': 'failed', 'message': 'Senha inválida'}), 401
            else:
                # fallback apenas para DEV
                if password != "s3cr3ty":
                    return jsonify({'status': 'failed', 'message': 'Senha inválida'}), 401

            access_token = create_access_token(identity={'username': username, 'role': 'admin'})
            return jsonify({'status': 'success', 'message': 'Login bem-sucedido!', 'token': access_token}), 200

        return jsonify({'status': 'failed', 'message': 'Usuário inválido'}), 401

    # --- MONITOR STATUS ---
    @app_instance.route('/api/monitor-status', methods=['GET'])
    def monitor_status():
        try:
            status_info = monitorar_status_visitantes()
            if status_info is not None:
                return jsonify(status_info), 200
            else:
                return jsonify({"error": "Erro ao monitorar status."}), 500
        except Exception as e:
            logging.error(f"Erro ao monitorar status: {e}")
            return jsonify({"error": str(e)}), 500

    # --- REGISTRO DE VISITANTE ---
    @app_instance.route('/api/register', methods=['POST'])
    def register():
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

    # --- WEBHOOK TWILIO ---
    @app_instance.route('/api/webhook', methods=['POST'])
    def webhook():
        try:
            data = request.form
            from_number = data.get('From', '')
            message_body = data.get('Body', '').strip()
            message_sid = data.get('MessageSid', '')
            logging.info(f"Recebendo mensagem: {from_number}, SID: {message_sid}, Msg: {message_body}")
            processar_mensagem(from_number, message_body, message_sid)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logging.error(f"Erro no webhook: {e}")
            return jsonify({"error": "Erro ao processar webhook"}), 500

    @app_instance.route('/api/get-visitors', methods=['GET'])
    def api_get_visitors():
        """Lista visitantes básicos (para envio manual WhatsApp)."""
        try:
            visitantes = listar_todos_visitantes()

            visitors = []
            for v in visitantes:
                # Caso seja dict (MySQL com dictionary=True)
                if isinstance(v, dict):
                    visitors.append({
                        "id": v.get("id"),
                        "name": v.get("nome"),
                        "phone": v.get("telefone")
                    })
                else:
                    # Caso seja tupla ou sqlite3.Row
                    visitors.append({
                        "id": v[0],
                        "name": v[1],
                        "phone": v[2] if len(v) > 2 else None
                    })

            return jsonify({"status": "success", "visitors": visitors}), 200
        except Exception as e:
            logging.error(f"Erro em /api/get-visitors: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500


    @app_instance.route('/api/send-message-manual', methods=['POST'])
    def api_send_message_manual():
        """Envia mensagem manual via Twilio (1 a 1)."""
        try:
            data = request.get_json()
            numero = data.get("numero")
            params = data.get("params", {})
            content_sid = data.get("ContentSid")
            mensagem = data.get("mensagem", "")

            if not numero:
                return jsonify({"success": False, "error": "Número não informado"}), 400

            client = Client(TWILIO_SID, TWILIO_TOKEN)

            # Se vier ContentSid, usa template do Twilio
            if content_sid:
                message = client.messages.create(
                    from_=TWILIO_NUMBER,
                    to=f"whatsapp:{numero}",
                    content_sid=content_sid,
                    content_variables=params
                )
            else:
                message = client.messages.create(
                    from_=TWILIO_NUMBER,
                    to=f"whatsapp:{numero}",
                    body=mensagem
                )

            logging.info(f"✅ Mensagem enviada via Twilio para {numero}, SID: {message.sid}")
            return jsonify({"success": True, "sid": message.sid}), 200
        except Exception as e:
            logging.error(f"Erro em /api/send-message-manual: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # --- DASHBOARD ---
    @app_instance.route('/api/get-dashboard-data', methods=['GET'])
    def get_dashboard_data():
        try:
            total_visitantes = obter_total_visitantes()
            total_membros, total_homens_membro, total_mulheres_membro = obter_total_membros()
            total_discipulados, total_homens_discipulado, total_mulheres_discipulado = obter_total_discipulados()
            dados_genero = obter_dados_genero()

            return jsonify({
                "totalVisitantes": total_visitantes,
                "totalMembros": total_membros,
                "totalhomensMembro": total_homens_membro,
                "totalmulheresMembro": total_mulheres_membro,
                "discipuladosAtivos": total_discipulados,
                "totalHomensDiscipulado": total_homens_discipulado,
                "totalMulheresDiscipulado": total_mulheres_discipulado,
                "grupos_comunhao": 0,
                "Homens": dados_genero.get("Homens", 0),
                "Homens_Percentual": dados_genero.get("Homens_Percentual", 0),
                "Mulheres": dados_genero.get("Mulheres", 0),
                "Mulheres_Percentual": dados_genero.get("Mulheres_Percentual", 0)
            }), 200
        except Exception as e:
            logging.error(f"Erro no get-dashboard-data: {e}")
            return jsonify({"error": str(e)}), 500

    # --- VISITANTES / ESTATÍSTICAS ---
    @app_instance.route('/api/visitantes', methods=['GET'])
    def get_all_visitantes():
        try:
            visitantes = listar_todos_visitantes()
            return jsonify(visitantes), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/api/fases-visitantes', methods=['GET'])
    def get_fases_visitantes():
        try:
            fases = visitantes_listar_fases()
            return jsonify(fases), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/api/estatisticas-visitantes', methods=['GET'])
    def get_estatisticas_visitantes():
        try:
            estatisticas = visitantes_listar_estatisticas()
            return jsonify(estatisticas), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- HEALTH CHECK ---
    @app_instance.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "alive",
            "message": "Bot Integra+ ativo!",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    # --- ADMIN IA ---
    @app_instance.route('/admin/integra/learn')
    def integra_learn_dashboard():
        if not session.get('integra_admin_logged_in'):
            return redirect(url_for('login_page'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, question, created_at FROM unknown_questions WHERE status='pending' ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        questions = [{"id": r[0], "user_id": r[1], "question": r[2], "created_at": r[3]} for r in rows]
        cursor.close(); conn.close()
        return render_template('admin_integra_learn.html', questions=questions)

    @app_instance.route('/api/ia/pending-questions', methods=['GET'])
    def ia_pending_questions():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, question, created_at
                FROM unknown_questions
                WHERE status='pending'
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            cursor.close(); conn.close()

            perguntas = [
                {
                    "id": r.get("id"),
                    "user_id": r.get("user_id"),
                    "question": r.get("question"),
                    "created_at": r.get("created_at"),
                }
                for r in rows
            ]
            return jsonify({"questions": perguntas}), 200
        except Exception as e:
            logging.error(f"Erro em /api/ia/pending-questions: {e}")
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/api/ia/training-list', methods=['GET'])
    def ia_training_list():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, question, answer, category, fonte, updated_at FROM training_pairs ORDER BY updated_at DESC LIMIT 100")
            rows = cursor.fetchall()
            pares = [{"id": r[0], "question": r[1], "answer": r[2], "category": r[3], "fonte": r[4], "updated_at": r[5]} for r in rows]
            cursor.close(); conn.close()
            return jsonify({"training_pairs": pares}), 200
        except Exception as e:
            logging.error(f"Erro em /api/ia/training-list: {e}")
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/api/ia/teach', methods=['POST'])
    def ia_teach():
        try:
            data = request.get_json()
            question = data.get('question', '').strip()
            answer = data.get('answer', '').strip()
            category = data.get('category', '').strip()

            if not all([question, answer, category]):
                return jsonify({"error": "Campos obrigatórios"}), 400

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO training_pairs (question, answer, category, fonte, created_at, updated_at)
                VALUES (%s, %s, %s, 'manual', NOW(), NOW())
                ON DUPLICATE KEY UPDATE answer = VALUES(answer), updated_at = NOW()
            """, (question, answer, category))
            cursor.execute("UPDATE unknown_questions SET status = 'answered' WHERE question = %s", (question,))
            conn.commit()
            cursor.close(); conn.close()
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logging.error(f"Erro em /api/ia/teach: {e}")
            return jsonify({"error": str(e)}), 500

    # --- EVENTOS ---
    @app_instance.route('/api/eventos/filtrar', methods=['POST'])
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

    @app_instance.route('/api/eventos/enviar', methods=['POST'])
    def api_eventos_enviar():
        try:
            data = request.json
            logging.info(f"📩 Dados recebidos para campanha: {data}")
    
            evento_nome = data.get("evento_nome")
            mensagem = data.get("mensagem")
            imagem_url = data.get("imagem_url")
            visitantes = data.get("visitantes")
    
            if not visitantes or not evento_nome or not mensagem:
                return jsonify({"status": "error", "message": "Dados incompletos para envio"}), 400
    
            ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
            ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
            ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")
            if not ZAPI_INSTANCE or not ZAPI_TOKEN or not ZAPI_CLIENT_TOKEN:
                logging.error("❌ Variáveis do Z-API não configuradas!")
                return jsonify({"status": "error", "message": "Configuração Z-API ausente"}), 500
    
            headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}
            enviados, falhas = [], []
    
            for v in visitantes:
                visitante_id = v.get("id")
                telefone = v.get("telefone")
                if not telefone:
                    falhas.append({"id": visitante_id, "motivo": "telefone ausente"})
                    continue
    
                telefone_envio = f"55{telefone}" if not telefone.startswith("55") else telefone
                try:
                    if imagem_url:
                        payload = {"phone": telefone_envio, "caption": mensagem, "image": imagem_url}
                        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
                    else:
                        payload = {"phone": telefone_envio, "message": mensagem}
                        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    
                    logging.info(f"➡️ Enviando para {telefone_envio} via {url}")
                    response = requests.post(url, json=payload, headers=headers, timeout=15)
                    status = "enviado" if response.ok else f"falha: {response.status_code}"
                    salvar_envio_evento(visitante_id, evento_nome, mensagem, imagem_url, status)
                    enviados.append({"id": visitante_id, "telefone": telefone_envio, "status": status})
    
                except Exception as e:
                    logging.error(f"❌ Erro ao enviar para {telefone_envio}: {e}")
                    salvar_envio_evento(visitante_id, evento_nome, mensagem, imagem_url, "erro")
                    falhas.append({"id": visitante_id, "telefone": telefone_envio, "status": "erro"})
    
            return jsonify({"status": "success", "enviados": enviados, "falhas": falhas}), 200
        except Exception as e:
            logging.exception("Erro em /api/eventos/enviar")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app_instance.route('/api/eventos/envios', methods=['GET'])
    def api_eventos_envios():
        try:
            envios = listar_envios_eventos()
            return jsonify({"status": "success", "envios": envios}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/envios: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app_instance.route('/api/eventos/reprocessar', methods=['POST'])
    def api_eventos_reprocessar():
        try:
            data = request.json
            evento_nome = data.get("evento_nome")
    
            if not evento_nome:
                return jsonify({"status": "error", "message": "Evento não informado"}), 400
    
            ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
            ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
            ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")
            headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}
    
            enviados = []
            falhas = []
            lote_size = 20
    
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
    
            # Selecionar apenas os que deram erro
            cursor.execute("""
                SELECT ee.id as envio_id, v.id as visitante_id, v.telefone
                FROM eventos_envios ee
                JOIN visitantes v ON v.id = ee.visitante_id
                WHERE ee.evento_nome = %s AND ee.status = 'erro'
            """, (evento_nome,))
            pendentes = cursor.fetchall()
    
            total = len(pendentes)
            logging.info(f"🔄 Reprocessando {total} envios com erro para o evento {evento_nome}")
    
            for i in range(0, total, lote_size):
                lote = pendentes[i:i + lote_size]
                for p in lote:
                    visitante_id = p["visitante_id"]
                    telefone = p["telefone"]
                    telefone_envio = f"55{telefone}" if telefone and not telefone.startswith("55") else telefone
    
                    try:
                        # Pega a mensagem original do envio
                        cursor.execute("""
                            SELECT mensagem, imagem_url 
                            FROM eventos_envios 
                            WHERE id = %s
                        """, (p["envio_id"],))
                        row = cursor.fetchone()
                        mensagem = row["mensagem"]
                        imagem_url = row["imagem_url"]
    
                        # Envia novamente
                        if imagem_url:
                            payload = {"phone": telefone_envio, "caption": mensagem, "image": imagem_url}
                            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
                        else:
                            payload = {"phone": telefone_envio, "message": mensagem}
                            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    
                        response = requests.post(url, json=payload, headers=headers, timeout=15)
                        status = "enviado" if response.ok else f"falha: {response.status_code}"
    
                        # Atualiza o registro existente
                        cursor.execute("""
                            UPDATE eventos_envios SET status = %s, data_envio = NOW()
                            WHERE id = %s
                        """, (status, p["envio_id"]))
                        conn.commit()
    
                        enviados.append({"id": visitante_id, "telefone": telefone_envio, "status": status})
                    except Exception as e:
                        logging.error(f"Erro ao reprocessar visitante {visitante_id}: {e}")
                        falhas.append({"id": visitante_id, "telefone": telefone_envio, "status": "erro"})
    
                import time
                time.sleep(2)  # pausa entre lotes
    
            cursor.close()
            conn.close()
    
            return jsonify({"status": "success", "reprocessados": enviados, "falhas": falhas}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/reprocessar: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
