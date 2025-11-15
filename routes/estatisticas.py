import logging
from flask import jsonify, request
from database import get_db_connection


def fetch_all_dict(cursor):
    """Converte resultados tuple → dict automaticamente."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_one_dict(cursor):
    """Converte uma única linha tuple → dict automaticamente."""
    row = cursor.fetchone()
    if row is None:
        return {}
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def register(app):

    # ============================================================
    # 1) ESTATÍSTICAS GERAIS
    # ============================================================
    @app.route('/api/estatisticas/geral', methods=['GET'])
    def estatisticas_geral():
        try:
            meses = int(request.args.get("meses", 6))
            conn = get_db_connection()
            cursor = conn.cursor()

            filtro_data = ""
            if meses > 0:
                filtro_data = f"WHERE v.data_cadastro >= DATE_SUB(CURDATE(), INTERVAL {meses} MONTH)"

            # ----------------------- INÍCIO -----------------------
            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {filtro_data} AND f.descricao = 'INICIO';
            """)
            inicio = fetch_one_dict(cursor)

            # ----------------------- GÊNERO -----------------------
            cursor.execute(f"""
                SELECT 
                    SUM(v.genero='masculino') AS homens,
                    SUM(v.genero='feminino') AS mulheres,
                    COUNT(*) AS total
                FROM visitantes v
                {filtro_data};
            """)
            genero = fetch_one_dict(cursor)

            # ----------------------- DISCIPULADO -----------------------
            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total_discipulado
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {filtro_data} AND f.descricao LIKE '%DISCIPULADO%';
            """)
            discipulado = fetch_one_dict(cursor)

            # ----------------------- ORAÇÃO -----------------------
            cursor.execute(f"""
                SELECT COUNT(*) AS total_pedidos
                FROM visitantes v
                {filtro_data} AND v.pedido_oracao IS NOT NULL;
            """)
            oracao = fetch_one_dict(cursor)

            # ----------------------- ORIGEM -----------------------
            cursor.execute(f"""
                SELECT COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem,
                       COUNT(v.id) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.indicacao
                ORDER BY total DESC;
            """)
            origem = fetch_all_dict(cursor)

            # ----------------------- MENSAL -----------------------
            cursor.execute(f"""
                SELECT DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes, COUNT(v.id) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY mes
                ORDER BY mes DESC;
            """)
            mensal = fetch_all_dict(cursor)

            # ----------------------- CONVERSAS -----------------------
            cursor.execute("""
                SELECT 
                    SUM(tipo='enviada') AS enviadas,
                    SUM(tipo='recebida') AS recebidas
                FROM conversas;
            """)
            conversas = fetch_one_dict(cursor)

            # ----------------------- FASES -----------------------
            cursor.execute("""
                SELECT 
                    COALESCE(f.descricao, 'SEM FASE') AS fase,
                    COUNT(v.id) AS total
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                GROUP BY f.descricao
                ORDER BY total DESC;
            """)
            fases = fetch_all_dict(cursor)

            # ----------------------- DEMOGRAFIA -----------------------
            cursor.execute(f"""
                SELECT 
                    ROUND(AVG(TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE())), 1) AS idade_media,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 12 AND 17 THEN 1 ELSE 0 END) AS adolescentes,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 18 AND 29 THEN 1 ELSE 0 END) AS jovens,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 30 AND 59 THEN 1 ELSE 0 END) AS adultos,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) >= 60 THEN 1 ELSE 0 END) AS idosos
                FROM visitantes v
                {filtro_data};
            """)
            idade = fetch_one_dict(cursor)

            # ----------------------- ESTADO CIVIL -----------------------
            cursor.execute(f"""
                SELECT 
                    COALESCE(v.estado_civil, 'Não Informado') AS estado_civil,
                    COUNT(*) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.estado_civil
                ORDER BY total DESC
                LIMIT 10;
            """)
            estado_civil = fetch_all_dict(cursor)

            # ----------------------- CIDADES -----------------------
            cursor.execute(f"""
                SELECT 
                    COALESCE(v.cidade, 'Não Informada') AS cidade,
                    COUNT(*) AS total
                FROM visitantes v
                {filtro_data}
                GROUP BY v.cidade
                ORDER BY total DESC
                LIMIT 10;
            """)
            cidades = fetch_all_dict(cursor)

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
            logging.exception(e)
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # 2) KIDS
    # ============================================================
    @app.route('/api/estatisticas/kids', methods=['GET'])
    def estatisticas_kids():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    SUM(total_checkins) AS total_checkins,
                    SUM(alertas_enviados) AS alertas_enviados,
                    SUM(pai_veio) AS pai_veio
                FROM vw_performance_kids;
            """)
            totais = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT turma, SUM(total_checkins) AS total_checkins
                FROM vw_performance_kids
                GROUP BY turma
                ORDER BY turma;
            """)
            turmas = fetch_all_dict(cursor)

            cursor.close()
            conn.close()

            return jsonify({"totais": totais, "turmas": turmas})

        except Exception as e:
            logging.exception(e)
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # 3) FAMÍLIAS
    # ============================================================
    @app.route('/api/estatisticas/familias', methods=['GET'])
    def estatisticas_familias():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    COUNT(*) AS familias_ativas,
                    SUM(cestas_recebidas) AS total_cestas,
                    SUM(CASE WHEN necessidades_especificas IS NOT NULL 
                             AND necessidades_especificas != '' THEN 1 ELSE 0 END) AS necessidades
                FROM vw_familias_vulneraveis;
            """)
            totais = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT DATE(ultima_visita_kids) AS data,
                       COUNT(*) AS total
                FROM vw_familias_vulneraveis
                WHERE ultima_visita_kids IS NOT NULL
                GROUP BY DATE(ultima_visita_kids)
                ORDER BY data DESC
                LIMIT 15;
            """)
            visitas = fetch_all_dict(cursor)

            cursor.close()
            conn.close()

            return jsonify({"totais": totais, "visitas": visitas})

        except Exception as e:
            logging.exception(e)
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # 4) ALERTAS
    # ============================================================
    @app.route('/api/estatisticas/alertas', methods=['GET'])
    def estatisticas_alertas():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT tipo, mensagem, valor, cor FROM vw_alertas_pastorais;")
            alertas = fetch_all_dict(cursor)

            cursor.close()
            conn.close()

            return jsonify({"alertas": alertas})

        except Exception as e:
            logging.exception(e)
            return jsonify({"error": str(e)}), 500
