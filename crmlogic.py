# --- Importações de bibliotecas padrão ---
import logging
import os
from datetime import datetime

# --- Importações de bibliotecas externas ---
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# --- Configurações do Flask ---
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

# --- REMOVER A ROTA /health DAQUI - ELA JÁ EXISTE EM routes.py ---
# A rota /health deve ficar APENAS em routes.py

# --- CONFIGURAÇÃO DE LOGS ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
