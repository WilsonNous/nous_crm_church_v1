# crmlogic.py - patched entrypoint
import logging
import os
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS

try:
    from flask_jwt_extended import JWTManager
except Exception:
    # Fallback dummy JWTManager for environments sem flask_jwt_extended
    class JWTManager:
        def __init__(self, app=None):
            pass
    JWTManager = JWTManager


# --- APP BASE ---
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configurações
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # Em produção, usar expiração

jwt = JWTManager(app)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("✅ Aplicação Flask criada e configurada")


# --- REGISTRO DAS ROTAS ---
try:
    from routes import register_routes
    register_routes(app)  # Todas as rotas da API (/login, /get-dashboard-data, etc.)
    logging.info("✅ Rotas registradas com sucesso (routes.register_routes).")
except Exception as e:
    logging.exception("❌ Erro ao registrar rotas: %s", e)


# --- ROTAS FIXAS ---
@app.route("/", methods=["GET"])
def index():
    """Carrega o login sem expor querystring de usuário/senha"""
    return render_template("login.html")


@app.route("/health", methods=["GET"])
def _health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}, 200


# --- COMPATIBILIDADE GUNICORN ---
application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=os.getenv("FLASK_DEBUG", "0") == "1")
