import logging
from flask import render_template, jsonify, request
from database import get_db_connection

def register(app):

    # Página principal do painel de monitoramento
    @app.route('/app/monitor')
    def app_monitor_page():
        return render_template('app_monitor.html')

    # Endpoint: listar visitantes
    @app.route('/api/monitor/visitantes', methods=['GET'])
    def monitor_visitantes():
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, nome, telefone FROM visitantes ORDER BY nome ASC")
            visitantes = cursor.fetchall()
            cursor.close(); conn.close()
            return jsonify({"status": "success", "visitantes": visitantes}), 200
        except Exception as e:
            logging.error(f"Erro em /api/monitor/visitantes: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # Endpoint: listar conversas por visitante
    @app.route('/api/monitor/conversas/<int:visitante_id>', methods=['GET'])
    def monitor_conversas_visitante(visitante_id):
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT 
                    c.id, c.mensagem, c.tipo, c.data_hora,
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
            conversas = cursor.fetchall()
            cursor.close(); conn.close()
            return jsonify({"status": "success", "conversas": conversas}), 200
        except Exception as e:
            logging.error(f"Erro em /api/monitor/conversas/{visitante_id}: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
