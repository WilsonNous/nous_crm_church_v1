# Importações
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, redirect, url_for

# --- JWT compatibility shim ---
try:
    from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
except Exception:
    def create_access_token(identity):
        return f"MOCK_TOKEN_FOR_{identity}"

    def jwt_required(fn=None, *args, **kwargs):
        if fn is None:
            def wrapper(f):
                return f
            return wrapper
        return fn

    def get_jwt_identity():
        return None
# End shim

from werkzeug.security import generate_password_hash, check_password_hash
try:
    from twilio.twiml.messaging_response import MessagingResponse
except Exception:
    class MessagingResponse:
        def __init__(self):
            self._messages = []
        def message(self, text):
            self._messages.append(text)
            return text
        def to_xml(self):
            return '<Response>' + ''.join(f'<Message>{m}</Message>' for m in self._messages) + '</Response>'

import pandas as pd

from botmsg import processar_mensagem, enviar_mensagem_manual
from database import (salvar_visitante, visitante_existe,
                      normalizar_para_recebimento, listar_todos_visitantes,
                      monitorar_status_visitantes, listar_visitantes_fase_null,
                      visitantes_listar_fases, visitantes_listar_estatisticas,
                      visitantes_contar_discipulado_enviado, visitantes_contar_membros_interessados,
                      visitantes_contar_sem_retorno, visitantes_contar_sem_retorno_total,
                      visitantes_contar_sem_interesse_discipulado, visitantes_contar_novos,
                      salvar_conversa, atualizar_status, obter_conversa_por_visitante,
                      membro_existe, salvar_membro, obter_total_membros, obter_total_visitantes,
                      obter_total_discipulados, obter_dados_genero, get_db_connection)

from ia_integracao import IAIntegracao
ia_integracao = IAIntegracao()

UPLOAD_FOLDER = '/tmp/'
ALLOWED_EXTENSIONS = {'xlsx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def processar_excel(filepath):
    try:
        df = pd.read_excel(filepath)
        for _, row in df.iterrows():
            visitante_data = {
                'nome': row['Nome'],
                'telefone': str(row['Telefone']),
                'email': row.get('Email', None),
                'data_nascimento': row.get('Data de Nascimento', None),
                'cidade': row.get('Cidade', None),
                'genero': row.get('Gênero', None),
                'estado_civil': row.get('Estado Civil', None),
                'igreja_atual': row.get('Igreja Atual', None),
                'frequenta_igreja': 1 if row.get('Frequenta Igreja', 'Não').lower() == 'sim' else 0,
                'indicacao': row.get('Indicação', None),
                'membro': row.get('Membro', None),
                'pedido_oracao': row.get('Pedido de Oração', None),
                'horario_contato': row.get('Melhor Horário de Contato', None)
            }
            salvar_visitante(**visitante_data)
        return True
    except Exception as e:
        logging.error(f"Erro ao processar o arquivo Excel: {e}")
        return False

def register_routes(app_instance: Flask) -> None:

    # --- LOGIN ---
    @app_instance.route('/login', methods=['POST'])
    def login():
        data = request.get_json()
        if not data:
            return jsonify({'status': 'failed', 'message': 'Nenhum dado foi fornecido'}), 400
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return jsonify({'status': 'failed', 'message': 'Usuário e senha são obrigatórios'}), 400
        stored_username = 'admin'
        stored_hashed_password = generate_password_hash('s3cr3ty')
        if username == stored_username and check_password_hash(stored_hashed_password, password):
            access_token = create_access_token(identity={'username': username, 'role': 'admin'})
            return jsonify({'status': 'success','message': 'Login bem-sucedido!','token': access_token}), 200
        else:
            return jsonify({'status': 'failed','message': 'Usuário ou senha inválidos'}), 401

    # --- MONITOR STATUS ---
    @app_instance.route('/monitor-status', methods=['GET'])
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
    @app_instance.route('/register', methods=['POST'])
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
            'frequenta_igreja': 1 if data.get('attendingChurch') == 'true' else 0,
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
    @app_instance.route('/webhook', methods=['POST'])
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

    @app_instance.route('/get-dashboard-data', methods=['GET'])
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
                "grupos_comunhao": 0,  # se ainda não temos GC, deixa fixo
                "Homens": dados_genero.get("Homens", 0),
                "Homens_Percentual": dados_genero.get("Homens_Percentual", 0),
                "Mulheres": dados_genero.get("Mulheres", 0),
                "Mulheres_Percentual": dados_genero.get("Mulheres_Percentual", 0)
            }), 200
        except Exception as e:
            logging.error(f"Erro no get-dashboard-data: {e}")
            return jsonify({"error": str(e)}), 500

    # --- VISITANTES / ESTATÍSTICAS ---
    @app_instance.route('/visitantes', methods=['GET'])
    def get_all_visitantes():
        try:
            visitantes = listar_todos_visitantes()
            return jsonify(visitantes), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/fases-visitantes', methods=['GET'])
    def get_fases_visitantes():
        try:
            fases = visitantes_listar_fases()
            return jsonify(fases), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/estatisticas-visitantes', methods=['GET'])
    def get_estatisticas_visitantes():
        try:
            estatisticas = visitantes_listar_estatisticas()
            return jsonify(estatisticas), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # --- HEALTH CHECK ---
    @app_instance.route('/health', methods=['GET'])
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
            return redirect(url_for('integra_admin_login'))
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
            import traceback
            logging.error("Erro em /api/ia/pending-questions: %s", traceback.format_exc())
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
            logging.error(f"Erro: {e}")
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

