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

            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {filtro_data} AND f.descricao = 'INICIO';
            """)
            inicio = cursor.fetchone()

            cursor.execute(f"""
                SELECT SUM(v.genero='masculino') AS homens,
                       SUM(v.genero='feminino') AS mulheres,
                       COUNT(*) AS total
                FROM visitantes v
                {filtro_data};
            """)
            genero = cursor.fetchone()

            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total_discipulado
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {filtro_data} AND f.descricao LIKE '%DISCIPULADO%';
            """)
            discipulado = cursor.fetchone()

            cursor.execute(f"""
                SELECT COUNT(*) AS total_pedidos
                FROM visitantes v
                {filtro_data} AND v.pedido_oracao IS NOT NULL;
            """)
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

            # 🔹 Demografia
            cursor.execute(f"""
                SELECT ROUND(AVG(TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE())),1) AS idade_media,
                       SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 12 AND 17 THEN 1 ELSE 0 END) AS adolescentes,
                       SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 18 AND 29 THEN 1 ELSE 0 END) AS jovens,
                       SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 30 AND 59 THEN 1 ELSE 0 END) AS adultos,
                       SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) >= 60 THEN 1 ELSE 0 END) AS idosos
                FROM visitantes v
                {filtro_data};
            """)
            idade = cursor.fetchone()

            cursor.execute(f"""
                SELECT COALESCE(v.estado_civil, 'Não Informado') AS estado_civil, COUNT(*) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.estado_civil
                ORDER BY total DESC
                LIMIT 10;
            """)
            estado_civil = cursor.fetchall()

            cursor.execute(f"""
                SELECT COALESCE(v.cidade, 'Não Informada') AS cidade, COUNT(*) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.cidade
                ORDER BY total DESC
                LIMIT 10;
            """)
            cidades = cursor.fetchall()

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
                "fases": fases,
                "demografia": {
                    "idade": idade,
                    "estado_civil": estado_civil,
                    "cidades": cidades
                }
            }), 200

        except Exception as e:
            logging.error(f"Erro em estatísticas gerais: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
