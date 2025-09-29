# crmlogic.py - entrypoint com log de rotas
import logging
import os
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_cors import CORS

try:
    from flask_jwt_extended import JWTManager
except Exception:
    # Fallback dummy JWTManager para ambientes sem flask_jwt_extended
    class JWTManager:
        def __init__(self, app=None):
            pass
    JWTManager = JWTManager


# Criar a app Flask
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Configurações
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # em prod defina um tempo razoável

# JWT
jwt = JWTManager(app)

# Logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("✅ Aplicação Flask (app) criada e configurada com sucesso!")

# Flag para saber se as rotas foram registradas
routes_ok = False
routes_error = None

# Registrar rotas do routes.py
try:
    from routes import register_routes
    register_routes(app)
    logging.info("✅ Rotas registradas com sucesso (routes.register_routes).")
    routes_ok = True
except Exception as e:
    routes_error = str(e)
    logging.exception("❌ Erro ao registrar rotas: %s", e)

# DEBUG EXTRA: listar todas as rotas registradas
with app.app_context():
    for rule in app.url_map.iter_rules():
        logging.info(f"🔗 Rota registrada: {rule} -> {rule.endpoint}")

# Rota principal -> renderiza login.html
@app.route("/", methods=["GET"])
def login_page():
    return render_template("login.html")

# Health check
@app.route('/health', methods=['GET'])
def _health():
    return {'status': 'ok', 'time': datetime.utcnow().isoformat()}, 200

# Novo health para diagnosticar se /api/... está registrado
@app.route('/api/health', methods=['GET'])
def api_health():
    if not routes_ok:
        return jsonify({
            "status": "error",
            "message": "Rotas não registradas",
            "error": routes_error
        }), 500
    return jsonify({
        "status": "alive",
        "message": "Bot Integra+ ativo!",
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

# Alias p/ Gunicorn
application = app

# Rodar local
if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', '0') == '1'
    )
