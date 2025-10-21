# ============================================
# menu_routes.py
# Rotas de Navegação Principal do CRM Church
# ============================================

from flask import Blueprint, render_template

# Todas as páginas HTML sob /app
menu_bp = Blueprint("menu_bp", __name__, url_prefix="/app")

# =========================
# Páginas principais
# =========================
@menu_bp.route("/", methods=["GET"])
@menu_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")

@menu_bp.route("/menu", methods=["GET"])
def menu_page():
    return render_template("menu.html")

# =========================
# Estatísticas
# =========================
@menu_bp.route("/estatisticas", methods=["GET"])
def estatisticas_page():
    return render_template("estatisticas.html")

# =========================
# Cadastros
# =========================
@menu_bp.route("/visitantes", methods=["GET"])
def visitantes_page():
    return render_template("visitantes.html")

@menu_bp.route("/membros", methods=["GET"])
def membros_page():
    return render_template("membros.html")

@menu_bp.route("/acolhidos", methods=["GET"])
def acolhidos_page():
    return render_template("acolhidos.html")

# =========================
# Inteligência Artificial
# =========================
@menu_bp.route("/ia", methods=["GET"])
def ia_page():
    return render_template("ia.html")

# =========================
# Campanhas / Eventos
# =========================
@menu_bp.route("/campanhas", methods=["GET"])
def campanhas_page():
    return render_template("campanhas.html")

# =========================
# Monitores
# =========================
@menu_bp.route("/monitor-status", methods=["GET"])
def monitor_status_page():
    """Painel de Monitoramento de Status Pastoral"""
    return render_template("monitor-status.html")

@menu_bp.route("/monitor", methods=["GET"])
def monitor_conversas_page():
    """Painel de Conversas do Integra+"""
    return render_template("app_monitor.html")

# =========================
# WhatsApp
# =========================
@menu_bp.route("/whatsapp", methods=["GET"])
def whatsapp_page():
    return render_template("whatsapp.html")

# =========================
# Erros
# =========================
@menu_bp.app_errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404

@menu_bp.app_errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500
