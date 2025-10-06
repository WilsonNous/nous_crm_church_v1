# ============================================
# menu_routes.py
# Rotas de Navegação Principal do CRM Church
# ============================================

from flask import Blueprint, render_template

# Blueprint principal para páginas HTML
# Todas as rotas ficam sob o prefixo /app
menu_bp = Blueprint("menu_bp", __name__, url_prefix="/app")

# --------------------------
# Login / Página inicial
# --------------------------
@menu_bp.route("/", methods=["GET"])
@menu_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


# --------------------------
# Dashboard / Estatísticas
# --------------------------
@menu_bp.route("/estatisticas", methods=["GET"])
def estatisticas_page():
    return render_template("estatisticas.html")


# --------------------------
# Cadastros
# --------------------------
@menu_bp.route("/visitantes", methods=["GET"])
def visitantes_page():
    return render_template("visitantes.html")


@menu_bp.route("/membros", methods=["GET"])
def membros_page():
    return render_template("membros.html")


@menu_bp.route("/acolhidos", methods=["GET"])
def acolhidos_page():
    return render_template("acolhidos.html")


# --------------------------
# Inteligência Artificial
# --------------------------
@menu_bp.route("/ia", methods=["GET"])
def ia_page():
    return render_template("ia.html")


# --------------------------
# Campanhas / Eventos
# --------------------------
@menu_bp.route("/campanhas", methods=["GET"])
def campanhas_page():
    return render_template("campanhas.html")


# --------------------------
# Páginas de Erro Personalizadas
# --------------------------
@menu_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@menu_bp.app_errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500
