# routes/estatisticas.py
import logging
from flask import jsonify
from database import get_db_connection

def register(app):
    """
    Registra endpoints de estatísticas no app Flask.
    """

    # ===========================================================
    # 🔹 ENDPOINT ÚNICO: Estatísticas Gerais (todas em uma consulta)
    # ===========================================================
    @app.route('/api/estatisticas/geral', methods=['GET'])
    def estatisticas_geral():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Visitantes na fase INICIO
            cursor.execute("""
                SELECT COUNT(DISTINCT v.id) AS total
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                WHERE f.descricao = 'INICIO';
            """)
            inicio = cursor.fetchone()

            # Gênero
            cursor.execute("""
                SELECT 
                    SUM(v.genero = 'masculino') AS homens,
                    SUM(v.genero = 'feminino') AS mulheres,
                    COUNT(*) AS total
                FROM visitantes v;
            """)
            genero = cursor.fetchone()

            # Discipulado
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT v.id) AS total_discipulado
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                WHERE f.descricao LIKE '%DISCIPULADO%';
            """)
            discipulado = cursor.fetchone()

            # Pedidos de Oração
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_pedidos
                FROM visitantes v
                WHERE v.pedido_oracao IS NOT NULL;
            """)
            oracao = cursor.fetchone()

            # Origem dos Cadastros
            cursor.execute("""
                SELECT 
                    COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem,
                    COUNT(v.id) AS total
                FROM visitantes v
                GROUP BY v.indicacao
                ORDER BY total DESC;
            """)
            origem = cursor.fetchall()

            # Evolução Mensal
            cursor.execute("""
                SELECT 
                    DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes,
                    COUNT(v.id) AS total
                FROM visitantes v
                GROUP BY mes
                ORDER BY mes DESC;
            """)
            mensal = cursor.fetchall()

            # Conversas
            cursor.execute("""
                SELECT 
                    SUM(tipo = 'enviada') AS enviadas,
                    SUM(tipo = 'recebida') AS recebidas
                FROM conversas;
            """)
            conversas = cursor.fetchone()

            cursor.close()
            conn.close()

            # JSON final consolidado
            return jsonify({
                "inicio": inicio,
                "genero": genero,
                "discipulado": discipulado,
                "oracao": oracao,
                "origem": origem,
                "mensal": mensal,
                "conversas": conversas
            }), 200

        except Exception as e:
            logging.error(f"Erro em estatísticas gerais: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # ===========================================================
    # 🔹 ENDPOINTS INDEPENDENTES (mantidos para compatibilidade)
    # ===========================================================
    @app.route('/api/estatisticas/inicio', methods=['GET'])
    def estatisticas_inicio():
        return _run_query("""
            SELECT COUNT(DISTINCT v.id) AS total
            FROM visitantes v
            JOIN status s ON v.id = s.visitante_id
            JOIN fases f ON s.fase_id = f.id
            WHERE f.descricao = 'INICIO';
        """)

    @app.route('/api/estatisticas/genero', methods=['GET'])
    def estatisticas_genero():
        return _run_query("""
            SELECT 
                SUM(v.genero = 'masculino') AS homens,
                SUM(v.genero = 'feminino') AS mulheres,
                COUNT(*) AS total
            FROM visitantes v;
        """)

    @app.route('/api/estatisticas/discipulado', methods=['GET'])
    def estatisticas_discipulado():
        return _run_query("""
            SELECT 
                COUNT(DISTINCT v.id) AS total_discipulado
            FROM visitantes v
            JOIN status s ON v.id = s.visitante_id
            JOIN fases f ON s.fase_id = f.id
            WHERE f.descricao LIKE '%DISCIPULADO%';
        """)

    @app.route('/api/estatisticas/oracao', methods=['GET'])
    def estatisticas_oracao():
        return _run_query("""
            SELECT COUNT(*) AS total_pedidos
            FROM visitantes v
            WHERE v.pedido_oracao IS NOT NULL;
        """)

    @app.route('/api/estatisticas/origem', methods=['GET'])
    def estatisticas_origem():
        return _run_query("""
            SELECT 
                COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem,
                COUNT(v.id) AS total
            FROM visitantes v
            GROUP BY v.indicacao
            ORDER BY total DESC;
        """)

    @app.route('/api/estatisticas/mensal', methods=['GET'])
    def estatisticas_mensal():
        return _run_query("""
            SELECT 
                DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes,
                COUNT(v.id) AS total
            FROM visitantes v
            GROUP BY mes
            ORDER BY mes DESC;
        """)

    @app.route('/api/estatisticas/conversas', methods=['GET'])
    def estatisticas_conversas():
        return _run_query("""
            SELECT 
                SUM(tipo = 'enviada') AS enviadas,
                SUM(tipo = 'recebida') AS recebidas
            FROM conversas;
        """)


# =====================================================
# Função utilitária para rodar queries e padronizar saída
# =====================================================
def _run_query(sql):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # retorna objeto se só houver 1 linha
        if len(rows) == 1:
            return jsonify(rows[0]), 200
        return jsonify(rows), 200

    except Exception as e:
        logging.error(f"Erro em estatísticas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
