import logging
from flask import Blueprint, render_template, jsonify, request
from database import get_db_connection

monitor_bp = Blueprint("monitor_bp", __name__)

def register(app):
    app.register_blueprint(monitor_bp)


# ===========================
# Página principal do monitor
# ===========================
@monitor_bp.route('/app/monitor')
def monitor_page():
    return render_template('app_monitor.html')


# ===========================
# API — Listar Visitantes
# ===========================
@monitor_bp.route('/api/monitor/visitantes', methods=['GET'])
def monitor_visitantes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, telefone FROM visitantes ORDER BY nome ASC")

        columns = [col[0] for col in cursor.description]
        visitantes = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close(); conn.close()
        return jsonify({"status": "success", "visitantes": visitantes})
    except Exception as e:
        logging.error(f"Erro em /api/monitor/visitantes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ===========================
# API — Listar Conversas
# ===========================
@monitor_bp.route('/api/monitor/conversas/<int:visitante_id>', methods=['GET'])
def monitor_conversas_visitante(visitante_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.id,
                c.mensagem,
                c.tipo,
                c.data_hora,
                v.nome AS visitante_nome,
                CASE 
                    WHEN LOWER(c.tipo) = 'enviada' THEN 'Integra+'
                    WHEN LOWER(c.tipo) = 'recebida' THEN v.nome
                    ELSE 'Desconhecido'
                END AS autor
            FROM conversas c
            JOIN visitantes v ON v.id = c.visitante_id
            WHERE v.id = %s
            ORDER BY c.data_hora ASC
        """, (visitante_id,))

        columns = [col[0] for col in cursor.description]
        conversas = [dict(zip(columns, row)) for row in cursor.fetchall()]

        cursor.close(); conn.close()

        return jsonify({"status": "success", "conversas": conversas}), 200

    except Exception as e:
        logging.error(f"Erro em /api/monitor/conversas/{visitante_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
