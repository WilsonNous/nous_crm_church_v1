# routes/estatisticas.py
import logging
from flask import jsonify
from database import get_db_connection

def register(app):
    @app.route('/api/estatisticas/inicio', methods=['GET'])
    def estatisticas_inicio():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT v.id, v.nome, v.telefone, v.cidade, v.data_cadastro,
                       MAX(c.data_hora) AS ultima_interacao
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                LEFT JOIN conversas c ON v.id = c.visitante_id
                WHERE f.descricao = 'INICIO'
                GROUP BY v.id, v.nome, v.telefone, v.cidade, v.data_cadastro
                ORDER BY ultima_interacao DESC;
            """)

            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            return jsonify({
                "status": "success",
                "total": len(rows),
                "visitantes": rows
            }), 200
        except Exception as e:
            logging.error(f"Erro em /api/estatisticas/inicio: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
