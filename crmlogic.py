# crmlogic.py - entrypoint com log de rotas
import logging
import os
from datetime import datetime
from flask import Flask, jsonify, redirect, url_for
from flask_cors import CORS
from menu_routes import menu_bp

try:
    from flask_jwt_extended import JWTManager
except Exception:
    class JWTManager:
        def __init__(self, app=None):
            pass
    JWTManager = JWTManager

# --------------------------
# Inicialização do Flask
# --------------------------
app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key_para_dev')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', app.config['SECRET_KEY'])
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False

jwt = JWTManager(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("✅ Aplicação Flask criada e configurada com sucesso!")

# --------------------------
# Registrar rotas da API
# --------------------------
routes_ok = False
routes_error = None
try:
    from routes import register_routes
    from routes import campanhas  # 👈 importa o módulo inteiro
    register_routes(app)
    campanhas.register(app)       # 👈 chama a função register(app)
    routes_ok = True
    logging.info("✅ Rotas API registradas com sucesso.")
except Exception as e:
    routes_error = str(e)
    logging.exception("❌ Erro ao registrar rotas: %s", e)

# --------------------------
# Registrar Blueprint do Menu (páginas HTML)
# --------------------------
app.register_blueprint(menu_bp)
logging.info("✅ Blueprint 'menu_bp' registrado com prefixo /app.")

# --------------------------
# Redirecionar / para /app/login
# --------------------------
@app.route("/", methods=["GET"])
def redirect_to_login():
    return redirect(url_for("menu_bp.login_page"))

# --------------------------
# Health Checks
# --------------------------
@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}, 200

@app.route("/api/health", methods=["GET"])
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
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

# --------------------------
# Gunicorn alias
# --------------------------
application = app

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
