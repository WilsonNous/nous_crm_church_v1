# crmlogic.py - entrypoint com log de rotas (Render/Gunicorn friendly)

import os
import sys
import logging
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

# --------------------------
# LOGGING (Render/Gunicorn friendly)
# --------------------------
def setup_logging():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # remove handlers antigos (Gunicorn/Render às vezes já colocou)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Ajusta logs do werkzeug (Flask dev server). Em gunicorn, é menos relevante.
    logging.getLogger("werkzeug").setLevel(level)

setup_logging()
logging.info("🚀 Logging configurado (stdout). LOG_LEVEL=%s", os.getenv("LOG_LEVEL", "INFO"))

# --------------------------
# Inicialização do Flask
# --------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "fallback_secret_key_para_dev")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", app.config["SECRET_KEY"])
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = False

jwt = JWTManager(app)

logging.info("✅ Aplicação Flask criada e configurada com sucesso!")

# --------------------------
# Registrar rotas da API
# --------------------------
routes_ok = False
routes_error = None

try:
    from routes import register_routes
    from routes import campanhas  # importa o módulo inteiro

    register_routes(app)
    campanhas.register(app)

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
        return jsonify(
            {
                "status": "error",
                "message": "Rotas não registradas",
                "error": routes_error,
            }
        ), 500

    return jsonify(
        {
            "status": "alive",
            "message": "Bot Integra+ ativo!",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    ), 200

# --------------------------
# Gunicorn alias
# --------------------------
application = app

if __name__ == "__main__":
    # Em produção (Render) você usa gunicorn. Esse run abaixo é só para dev local.
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
