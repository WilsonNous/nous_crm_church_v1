import logging
from flask import jsonify, request
from database import get_db_connection

def register(app):
    @app.route('/api/estatisticas/geral', methods=['GET'])
    def estatisticas_geral():
        try:
            meses = int(request.args.get('meses', 6))
            conn = get_db_connection()
            cursor = conn.cursor()

            filtro_data = ""
            if meses > 0:
                filtro_data = f"WHERE v.data_cadastro >= DATE_SUB(CURDATE(), INTERVAL {meses} MONTH)"

            cursor.execute("""
                SELECT COUNT(DISTINCT v.id) AS total
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                WHERE f.descricao = 'INICIO';
            """)
            inicio = cursor.fetchone()

            cursor.execute("SELECT SUM(v.genero='masculino') AS homens, SUM(v.genero='feminino') AS mulheres, COUNT(*) AS total FROM visitantes v;")
            genero = cursor.fetchone()

            cursor.execute("""
                SELECT COUNT(DISTINCT v.id) AS total_discipulado
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                WHERE f.descricao LIKE '%DISCIPULADO%';
            """)
            discipulado = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) AS total_pedidos FROM visitantes v WHERE v.pedido_oracao IS NOT NULL;")
            oracao = cursor.fetchone()

            cursor.execute(f"""
                SELECT COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem, COUNT(v.id) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.indicacao
                ORDER BY total DESC;
            """)
            origem = cursor.fetchall()

            cursor.execute(f"""
                SELECT DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes, COUNT(v.id) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY mes
                ORDER BY mes DESC;
            """)
            mensal = cursor.fetchall()

            cursor.execute("SELECT SUM(tipo='enviada') AS enviadas, SUM(tipo='recebida') AS recebidas FROM conversas;")
            conversas = cursor.fetchone()

            cursor.execute("""
                SELECT COALESCE(f.descricao, 'SEM FASE') AS fase, COUNT(v.id) AS total
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                GROUP BY f.descricao
                ORDER BY total DESC;
            """)
            fases = cursor.fetchall()

            cursor.close()
            conn.close()

            return jsonify({
                "inicio": inicio,
                "genero": genero,
                "discipulado": discipulado,
                "oracao": oracao,
                "origem": origem,
                "mensal": mensal,
                "conversas": conversas,
                "fases": fases
            }), 200

        except Exception as e:
            logging.error(f"Erro em estatísticas gerais: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
