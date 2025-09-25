# --- Importações de bibliotecas padrão ---
import logging
import os
from datetime import datetime

# --- Importações de bibliotecas externas ---
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# --- Configurações do Flask ---
# ⚠️ MUDANÇA CRÍTICA: Exportar como 'application' para o Render
application = Flask(__name__)
CORS(application)

# --- FORÇAR A DEFINIÇÃO DA SECRET KEY ---
flask_secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
if not flask_secret_key or flask_secret_key == '':
    raise RuntimeError("FLASK_SECRET_KEY não definida! Verifique as variáveis de ambiente.")
application.secret_key = flask_secret_key

logging.info(f"✅ FLASK_SECRET_KEY definida como: {application.secret_key}")

# Configuração JWT
application.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default_secret_key')
jwt = JWTManager(application)

# --- LOG DE DEPURAÇÃO ---
logging.info("✅ Aplicação Flask configurada com sucesso!")

# --- REGISTRAR AS ROTAS (de routes.py) ---
from routes import register_routes
register_routes(application)

# --- NOVA ROTA: HEALTH CHECK PARA MANTER A APLICAÇÃO ACORDADA ---
@application.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint para verificar se a aplicação está viva.
    Usado para evitar que a instância do Render durma.
    """
    return {
        "status": "alive",
        "message": "Bot de Integração da Igreja Mais de Cristo Canasvieiras está ativo!",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, 200

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- REMOVIDO: if __name__ == "__main__": ---
# O Render não executa este bloco. Ele procura por 'application' no arquivo 'crmlogic.py'.
