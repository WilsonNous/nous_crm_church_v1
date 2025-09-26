# crmlogic.py - patched entrypoint
import logging
import os
from datetime import datetime
from flask import Flask, send_from_directory, render_template
from flask_cors import CORS
try:
    from flask_jwt_extended import JWTManager
except Exception:
    # Fallback dummy JWTManager for environments without flask_jwt_extended.
    class JWTManager:
        def __init__(self, app=None):
            pass
    JWTManager = JWTManager


# Create WSGI callable named 'app' (gunicorn expects module:app)
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configuration from environment
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
# JWT secret (use a strong secret in prod)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
# Disable default token expiry for simplicity; set a sensible expiry in production
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False

# Initialize JWT manager
jwt = JWTManager(app)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("✅ Aplicação Flask (app) criada e configurada com sucesso!")

# Register routes from routes.py
try:
    from routes import register_routes
    register_routes(app)
    logging.info("✅ Rotas registradas com sucesso (routes.register_routes).")
except Exception as e:
    logging.exception("Erro ao registrar rotas: %s", e)

# Rota principal -> renderiza login.html
@app.route("/", methods=["GET"])
def login_page():
    return render_template("login.html")

# Minimal health route if not provided by routes.py
@app.route('/health', methods=['GET'])
def _health():
    return {'status': 'ok', 'time': datetime.utcnow().isoformat()}, 200

# Alias para compatibilidade com gunicorn
application = app

# Allow running locally with `python crmlogic.py`
if __name__ == '__main__':
    # Recommended to run with gunicorn in production.
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG', '0') == '1')
