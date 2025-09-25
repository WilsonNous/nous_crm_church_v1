# Importações
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, url_for, render_template
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
from database import get_db_connection

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
                      obter_total_discipulados, obter_dados_genero)

application = Flask(__name__)
# Configuração da Chave Secreta para Sessões (OBRIGATÓRIO)
application.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
logging.info(f"FLASK_SECRET_KEY definida como: {application.secret_key}")

# Configuração JWT
application.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default_secret_key')
jwt = JWTManager(application)

# Configuração de Upload
UPLOAD_FOLDER = '/tmp/'
ALLOWED_EXTENSIONS = {'xlsx'}
application.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    """Verifica se o arquivo tem uma extensão permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def processar_excel(filepath):
    """Processa o arquivo Excel e salva os visitantes no banco de dados."""
    try:
        # Ler o arquivo Excel com pandas
        df = pd.read_excel(filepath)

        # Iterar pelas linhas do DataFrame e salvar os visitantes
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

            # Salvar o visitante no banco de dados
            salvar_visitante(**visitante_data)

        return True
    except Exception as e:
        logging.error(f"Erro ao processar o arquivo Excel: {e}")
        return False


def register_routes(app_instance: Flask) -> None:
    """Função responsável por registrar todas as rotas na aplicação."""

    # Rota de login com verificação de senha hash
    @app_instance.route('/login', methods=['POST'])
    def login():
        data = request.get_json()

        if not data:
            return jsonify({'status': 'failed', 'message': 'Nenhum dado foi fornecido'}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'status': 'failed', 'message': 'Usuário e senha são obrigatórios'}), 400

        # Definindo as credenciais de exemplo
        stored_username = 'admin'
        stored_hashed_password = generate_password_hash('s3cr3ty')  # Apenas para exemplo

        # Verificando se o usuário e a senha estão corretos
        if username == stored_username and check_password_hash(stored_hashed_password, password):
            # Criando o token JWT
            access_token = create_access_token(identity={'username': username, 'role': 'admin'})
            return jsonify({
                'status': 'success',
                'message': 'Login bem-sucedido!',
                'token': access_token
            }), 200
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Usuário ou senha inválidos'
            }), 401

    # Rota para monitorar status de visitantes e suas interações
    @app_instance.route('/monitor-status', methods=['GET'])
    def monitor_status():
        try:
            status_info = monitorar_status_visitantes()  # Chama a função do database.py

            if status_info is not None:
                return jsonify(status_info), 200
            else:
                logging.error("Erro ao monitorar status.")
                return jsonify({"error": "Erro ao monitorar status."}), 500
        except Exception as e:
            logging.error(f"Erro ao monitorar status: {e}")
            return jsonify({"error": str(e)}), 500

    # Rota para registrar um novo visitante no banco de dados
    @app_instance.route('/register', methods=['POST'])
    def register():
        data = request.get_json()

        if not data:
            logging.error("Nenhum dado enviado.")
            return jsonify({"error": "Nenhum dado enviado."}), 400

        telefone = normalizar_para_recebimento(data.get('phone'))
        if visitante_existe(telefone):
            logging.warning(f"Visitante com este telefone já cadastrado: {telefone}")
            return jsonify({"error": "Visitante com este telefone já cadastrado."}), 400

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
                logging.info("Cadastro realizado com sucesso.")
                # Chama o bot para iniciar a interação com o visitante
                # processar_mensagem(telefone, "iniciar", "")
                return jsonify({"message": "Cadastro realizado com sucesso!"}), 201
            else:
                logging.error("Erro ao cadastrar visitante no banco de dados.")
                return jsonify({"error": "Erro ao cadastrar visitante."}), 500
        except Exception as e:
            logging.exception(f"Erro ao salvar visitante: {e}")
            return jsonify({"error": "Erro interno do servidor. Tente novamente mais tarde."}), 500

    @app_instance.route('/register_member', methods=['POST'])
    def register_member():
        data = request.get_json()

        if not data:
            logging.error("Nenhum dado enviado.")
            return jsonify({"error": "Nenhum dado enviado."}), 400

        telefone = normalizar_para_recebimento(data.get('phone'))
        if membro_existe(telefone):
            logging.warning(f"Membro com este telefone já cadastrado: {telefone}")
            return jsonify({"error": "Membro com este telefone já cadastrado."}), 400

        membro_data = {
            'nome': data.get('name'),
            'telefone': telefone,
            'email': data.get('email'),
            'data_nascimento': data.get('birthdate'),
            'cep': data.get('cep'),
            'bairro': data.get('bairro'),
            'cidade': data.get('cidade'),
            'estado': data.get('estado'),
            'status_membro': data.get('membershipStatus', 'ativo')
        }

        try:
            if salvar_membro(**membro_data):
                logging.info("Cadastro de membro realizado com sucesso.")
                return jsonify({"message": "Cadastro de membro realizado com sucesso!"}), 201
            else:
                logging.error("Erro ao cadastrar membro no banco de dados.")
                return jsonify({"error": "Erro ao cadastrar membro."}), 500
        except Exception as e:
            logging.exception(f"Erro ao salvar membro: {e}")
            return jsonify({"error": "Erro interno do servidor. Tente novamente mais tarde."}), 500

    # Rota para enviar mensagens via WhatsApp
    @app_instance.route('/send-messages', methods=['POST'])
    def send_messages():
        data = request.get_json()

        if not data or 'messages' not in data:
            return jsonify({"error": "Dados de mensagem inválidos"}), 400

        messages = data['messages']
        for msg in messages:
            phone = msg.get('phone')
            message_body = msg.get('message')

            if not phone or not message_body:
                continue  # Ignora se faltar algum dado

            try:
                # Passar acao_manual=True para mensagens enviadas manualmente
                processar_mensagem(phone, message_body, "", acao_manual=True)
            except Exception as e:
                logging.error(f"Erro ao processar mensagem para o telefone {phone}: {e}")
                continue

        return jsonify({"status": "success", "message": "Mensagens enviadas com sucesso!"}), 200

    @app_instance.route('/webhook', methods=['POST'])
    def webhook():
        try:
            data = request.form
            from_number = data.get('From', '')
            message_body = data.get('Body', '').strip()
            message_sid = data.get('MessageSid', '')

            logging.info(f"Recebendo mensagem do número: {from_number}, SID: {message_sid}, Mensagem: {message_body}")

            # Processa a mensagem recebida
            processar_mensagem(from_number, message_body, message_sid)

            return jsonify({"status": "success", "message": "Webhook processado com sucesso"}), 200

        except Exception as e:
            logging.error(f"Erro ao processar o webhook do Twilio: {e}")
            return jsonify({"error": "Erro ao processar webhook"}), 500

    @app_instance.route('/visitantes', methods=['GET'])
    def get_all_visitantes():
        """Retorna todos os visitantes cadastrados."""
        try:
            visitantes = listar_todos_visitantes()

            if isinstance(visitantes, list):
                logging.info("Lista de visitantes retornada com sucesso.")
                return jsonify(visitantes), 200
            else:
                logging.error("Erro ao listar visitantes.")
                return jsonify(visitantes), 500
        except Exception as e:
            logging.exception(f"Erro no servidor ao listar visitantes: {e}")
            return jsonify({"error": "Erro interno do servidor."}), 500

    @app_instance.route('/get_visitors', methods=['GET'])
    def get_visitors():
        """Retorna todos os visitantes com a fase NULL (não iniciaram o processo)."""
        try:
            visitantes = listar_visitantes_fase_null()

            if visitantes is not None and len(visitantes) > 0:
                logging.info("Visitantes com fase NULL retornados com sucesso.")
                return jsonify({"status": "success", "visitors": visitantes}), 200
            else:
                logging.info("Nenhum visitante com fase NULL encontrado.")
                return jsonify({"status": "success", "visitors": []}), 200
        except Exception as e:
            logging.error(f"Erro ao listar visitantes com fase NULL: {e}")
            return jsonify({"error": "Erro ao listar visitantes."}), 500

    # Rota para consultar todas as fases de cada visitante
    @app_instance.route('/fases-visitantes', methods=['GET'])
    def get_fases_visitantes():
        try:
            fases = visitantes_listar_fases()
            return jsonify(fases), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Rota para consultar estatísticas gerais dos visitantes
    @app_instance.route('/estatisticas-visitantes', methods=['GET'])
    def get_estatisticas_visitantes():
        try:
            estatisticas = visitantes_listar_estatisticas()
            return jsonify(estatisticas), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar novos visitantes
    @app_instance.route('/visitantes/novos', methods=['GET'])
    def contar_novos():
        try:
            total_novos = visitantes_contar_novos()
            return jsonify({"novos_visitantes": total_novos}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar visitantes que desejam ser membros
    @app_instance.route('/visitantes/interessados-membro', methods=['GET'])
    def contar_interessados_membro():
        try:
            total_interessados = visitantes_contar_membros_interessados()
            return jsonify({"interessados_membro": total_interessados}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar visitantes que não deram retorno
    @app_instance.route('/visitantes/sem-retorno', methods=['GET'])
    def contar_sem_retorno():
        try:
            total_sem_retorno = visitantes_contar_sem_retorno()
            return jsonify({"sem_retorno": total_sem_retorno}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar visitantes que foram enviados ao discipulado
    @app_instance.route('/visitantes/discipulado-enviado', methods=['GET'])
    def contar_discipulado_enviado():
        try:
            total_enviados_discipulado = visitantes_contar_discipulado_enviado()
            return jsonify({"discipulado_enviado": total_enviados_discipulado}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar visitantes sem interesse no discipulado
    @app_instance.route('/visitantes/sem-interesse-discipulado', methods=['GET'])
    def contar_sem_interesse_discipulado():
        try:
            total_sem_interesse = visitantes_contar_sem_interesse_discipulado()
            return jsonify({"sem_interesse_discipulado": total_sem_interesse}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Endpoint para contar visitantes que não deram nenhum tipo de retorno
    @app_instance.route('/visitantes/sem-retorno-total', methods=['GET'])
    def contar_sem_retorno_total():
        try:
            total_sem_retorno_total = visitantes_contar_sem_retorno_total()
            return jsonify({"sem_retorno_total": total_sem_retorno_total}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app_instance.route("/send-message-manual", methods=["POST"])
    def send_message_manual():
        logging.info("Iniciando a função send_message_manual.")

        try:
            data = request.get_json()
            logging.info(f"Dados recebidos: {data}")

            numero = data.get('numero')
            template_sid = data.get('ContentSid')  # Mantenha ContentSid para garantir a consistência
            params = data.get('params')

            if not numero:
                logging.error("Número não fornecido.")
                return jsonify({"error": "Número não fornecido"}), 400
            if not template_sid:
                logging.error("Template não fornecido.")
                return jsonify({"error": "Template não fornecido"}), 400
            if params is None:
                logging.error("Parâmetros não fornecidos.")
                return jsonify({"error": "Parâmetros não fornecidos"}), 400

            logging.info(f"Número normalizado antes de envio: {numero}")

            numero_normalizado = normalizar_para_recebimento(numero)
            logging.info(f"Número normalizado: {numero_normalizado}")

            atualizar_status(numero_normalizado, "INICIO")
            logging.info(f"Status do visitante atualizado para 'INICIO'.")

            enviar_mensagem_manual(numero_normalizado, template_sid, params)  # Chamando a função com template_sid

            salvar_conversa(numero_normalizado, 'Mensagem Template Inicial', tipo='enviada')
            logging.info("Conversa salva no banco de dados.")

            return jsonify({"success": True}), 200
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem manual: {e}")
            return jsonify({"error": str(e)}), 500

    # Definir o endpoint que busca a conversa de um visitante específico
    @app_instance.route('/api/conversas/<int:visitante_id>', methods=['GET'])
    def get_conversa(visitante_id):
        try:
            conversa = obter_conversa_por_visitante(visitante_id)

            if not conversa:
                return "<p>Conversa não encontrada.</p>", 404

            return conversa, 200

        except Exception as e:
            logging.error(f"Erro ao buscar conversa para o visitante {visitante_id}: {e}")
            return jsonify({"error": str(e)}), 500

    @app_instance.route('/sms', methods=['POST'])
    def sms_reply():
        # Receber a mensagem
        msg_body = request.form.get('Body')
        sender = request.form.get('From')

        # Processar a mensagem conforme necessário
        print(f'Mensagem recebida de {sender}: {msg_body}')

        # Responder à mensagem (opcional)
        resp = MessagingResponse()
        resp.message("Recebido! Obrigado pelo seu contato.")
        return str(resp)

    @app_instance.route('/get-dashboard-data', methods=['GET'])
    def get_dashboard_data():
        try:
            # Busca cada totalizador individualmente
            total_visitantes = obter_total_visitantes()
            total_membros, total_homensmembro, total_mulheresmembro = obter_total_membros()

            # Busca o total de discipulados, incluindo totais por gênero
            discipulados_ativos, total_homens_discipulado, total_mulheres_discipulado = obter_total_discipulados()

            # Obtém dados de gênero (Homens e Mulheres) com uma nova função
            dados_genero = obter_dados_genero()

            # Constrói o dicionário de dados do dashboard
            dashboard_data = {
                "totalVisitantes": total_visitantes,
                "Homens": dados_genero["Homens"],
                "Homens_Percentual": dados_genero["Homens_Percentual"],
                "Mulheres": dados_genero["Mulheres"],
                "Mulheres_Percentual": dados_genero["Mulheres_Percentual"],
                "totalMembros": total_membros,
                "totalhomensMembro": total_homensmembro,
                "totalmulheresMembro": total_mulheresmembro,
                "discipuladosAtivos": discipulados_ativos,
                "totalHomensDiscipulado": total_homens_discipulado,
                "totalMulheresDiscipulado": total_mulheres_discipulado
            }

            # Retorna os dados em formato JSON
            return jsonify(dashboard_data), 200

        except Exception as e:
            logging.error(f"Erro ao obter dados do dashboard: {e}")
            return jsonify({"error": str(e)}), 500

    # --- NOVA ROTA: HEALTH CHECK PARA MANTER A APLICAÇÃO ACORDADA ---
    @app_instance.route('/health', methods=['GET'])
    def health_check():
        """
        Endpoint para verificar se a aplicação está viva.
        Usado para evitar que a instância do Render durma.
        """
        return jsonify({
            "status": "alive",
            "message": "Bot de Integração da Igreja Mais de Cristo está ativo!",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200

    # --- NOVAS ROTAS DE ADMINISTRAÇÃO PARA O INTEGRA+ ---

    @app_instance.route('/admin/integra/login', methods=['GET', 'POST'])
    def integra_admin_login():
        if request.method == 'POST':
            password = request.form.get('password')
            correct_password = os.getenv('ADMIN_PASSWORD', 's3cr3ty')
            if password == correct_password:
                session['integra_admin_logged_in'] = True
                return redirect(url_for('integra_learn_dashboard'))
            return '<script>alert("Senha incorreta!"); window.location="/admin/integra/login";</script>', 401
        return '''
            <html><body style="font-family:Arial;text-align:center;padding:50px;">
                <h3>🔐 Login Admin - Integra+</h3>
                <form method="post" style="display:inline-block;text-align:left;">
                    <input type="password" name="password" placeholder="Senha" required style="padding:10px;
                    width:300px;"><br><br>
                    <button type="submit" style="padding:10px 20px;background:#007bff;color:white;border:none;
                    ">Entrar</button>
                </form>
            </body></html>
        '''

    @app_instance.route('/admin/integra/learn')
    def integra_learn_dashboard():
        if not session.get('integra_admin_logged_in'):
            return redirect(url_for('integra_admin_login'))

        conn = get_db_connection()
        if not conn:
            return "Erro de conexão", 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, user_id, question, created_at FROM unknown_questions 
            WHERE status = 'pending' ORDER BY created_at DESC LIMIT 50
        """)
        questions = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template('admin_integra_learn.html', questions=questions)

    @app_instance.route('/admin/integra/teach', methods=['POST'])
    def teach_integra():
        if not session.get('integra_admin_logged_in'):
            return jsonify({'error': 'Acesso negado'}), 403

        data = request.get_json()
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        category = data.get('category', '').strip()

        if not all([question, answer, category]):
            return jsonify({"error": "Campos obrigatórios"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Erro de conexão"}), 500

        cursor = conn.cursor()
        try:
            # Inserir na knowledge_base
            cursor.execute("""
                INSERT INTO knowledge_base (question, answer, category, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE answer = VALUES(answer), updated_at = NOW()
            """, (question, answer, category))

            # Marcar como respondida
            cursor.execute("UPDATE unknown_questions SET status = 'answered' WHERE question = %s", (question,))
            conn.commit()
            return jsonify({"status": "success"})
        except Exception as e:
            conn.rollback()
            return jsonify({"error": str(e)}), 500
        finally:
            cursor.close()
            conn.close()


# Chamada para registrar as rotas
register_routes(application)


