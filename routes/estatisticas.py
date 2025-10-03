# routes/estatisticas.py
import logging
from flask import jsonify
from database import get_db_connection

def register(app):
    """
    Registra endpoints de estatísticas no app Flask.
    """

    # 🔹 Visitantes na fase INICIO
    @app.route('/api/estatisticas/inicio', methods=['GET'])
    def estatisticas_inicio():
        return _run_query("""
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

    # 🔹 Distribuição por fases
    @app.route('/api/estatisticas/fases', methods=['GET'])
    def estatisticas_fases():
        return _run_query("""
            SELECT COALESCE(f.descricao, 'SEM FASE') AS fase, COUNT(v.id) AS total
            FROM visitantes v
            LEFT JOIN status s ON v.id = s.visitante_id
            LEFT JOIN fases f ON s.fase_id = f.id
            GROUP BY f.descricao
            ORDER BY total DESC;
        """)

    # 🔹 Última interação de cada visitante
    @app.route('/api/estatisticas/interacoes', methods=['GET'])
    def estatisticas_interacoes():
        return _run_query("""
            SELECT v.id, v.nome, v.telefone,
                   MAX(c.data_hora) AS ultima_interacao,
                   COUNT(c.id) AS total_interacoes
            FROM visitantes v
            LEFT JOIN conversas c ON v.id = c.visitante_id
            GROUP BY v.id, v.nome, v.telefone
            ORDER BY ultima_interacao DESC;
        """)

    # 🔹 Resumo por gênero
    @app.route('/api/estatisticas/genero', methods=['GET'])
    def estatisticas_genero():
        return _run_query("""
            SELECT 
                SUM(CASE WHEN v.genero = 'masculino' THEN 1 ELSE 0 END) AS homens,
                SUM(CASE WHEN v.genero = 'feminino' THEN 1 ELSE 0 END) AS mulheres,
                COUNT(*) AS total
            FROM visitantes v;
        """)

    # 🔹 Discipulados (ativos, homens, mulheres)
    @app.route('/api/estatisticas/discipulado', methods=['GET'])
    def estatisticas_discipulado():
        return _run_query("""
            SELECT 
                COUNT(DISTINCT v.id) AS total_discipulado,
                SUM(CASE WHEN v.genero = 'masculino' THEN 1 ELSE 0 END) AS homens,
                SUM(CASE WHEN v.genero = 'feminino' THEN 1 ELSE 0 END) AS mulheres
            FROM visitantes v
            JOIN status s ON v.id = s.visitante_id
            JOIN fases f ON s.fase_id = f.id
            WHERE f.descricao LIKE '%DISCIPULADO%';
        """)

    # 🔹 Sem retorno (sem interações recentes)
    @app.route('/api/estatisticas/sem-retorno', methods=['GET'])
    def estatisticas_sem_retorno():
        return _run_query("""
            SELECT v.id, v.nome, v.telefone, v.cidade, v.data_cadastro
            FROM visitantes v
            LEFT JOIN conversas c ON v.id = c.visitante_id
            GROUP BY v.id, v.nome, v.telefone, v.cidade, v.data_cadastro
            HAVING MAX(c.data_hora) IS NULL
            ORDER BY v.data_cadastro DESC;
        """)

    # 🔹 Campanhas / eventos enviados
    @app.route('/api/estatisticas/eventos', methods=['GET'])
    def estatisticas_eventos():
        return _run_query("""
            SELECT e.evento_nome, COUNT(e.id) AS total_envios,
                   SUM(CASE WHEN e.status = 'sucesso' THEN 1 ELSE 0 END) AS enviados,
                   SUM(CASE WHEN e.status = 'erro' THEN 1 ELSE 0 END) AS erros
            FROM eventos_envios e
            GROUP BY e.evento_nome
            ORDER BY total_envios DESC;
        """)

    # 🔹 Pedidos de oração
    @app.route('/api/estatisticas/oracao', methods=['GET'])
    def estatisticas_oracao():
        return _run_query("""
            SELECT COUNT(*) AS total_pedidos,
                   SUM(CASE WHEN v.pedido_oracao IS NOT NULL THEN 1 ELSE 0 END) AS preenchidos
            FROM visitantes v;
        """)

    # 🔹 Origem dos cadastros
    @app.route('/api/estatisticas/origem', methods=['GET'])
    def estatisticas_origem():
        return _run_query("""
            SELECT COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem, COUNT(v.id) AS total
            FROM visitantes v
            GROUP BY v.indicacao
            ORDER BY total DESC;
        """)

    # 🔹 Visitantes por mês/ano
    @app.route('/api/estatisticas/mensal', methods=['GET'])
    def estatisticas_mensal():
        return _run_query("""
            SELECT DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes, COUNT(v.id) AS total
            FROM visitantes v
            GROUP BY mes
            ORDER BY mes DESC;
        """)

    # 🔹 Conversas totais
    @app.route('/api/estatisticas/conversas', methods=['GET'])
    def estatisticas_conversas():
        return _run_query("""
            SELECT COUNT(*) AS total_conversas,
                   SUM(CASE WHEN tipo = 'enviada' THEN 1 ELSE 0 END) AS enviadas,
                   SUM(CASE WHEN tipo = 'recebida' THEN 1 ELSE 0 END) AS recebidas
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
        return jsonify({"status": "success", "data": rows}), 200
    except Exception as e:
        logging.error(f"Erro em estatísticas: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
