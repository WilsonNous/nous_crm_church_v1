import logging
from flask import jsonify, request
from database import get_db_connection

# ============================================================
# HELPERS
# ============================================================
def fetch_all_dict(cursor):
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def fetch_one_dict(cursor):
    row = cursor.fetchone()
    if row is None:
        return {}
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


# ============================================================
# REGISTER
# ============================================================
def register(app):

    # ============================================================
    # 1) ESTATÍSTICAS GERAIS (VISITANTES + MEMBROS)
    # ============================================================
    @app.route('/api/estatisticas/geral', methods=['GET'])
    def estatisticas_geral():
        try:
            meses = int(request.args.get("meses", 6))
            conn = get_db_connection()
            cursor = conn.cursor()

            # ----------------------------------------------------
            # FILTROS DINÂMICOS (VISITANTES)
            # ----------------------------------------------------
            filtros_base = []
            if meses > 0:
                filtros_base.append(
                    f"v.data_cadastro >= DATE_SUB(CURDATE(), INTERVAL {meses} MONTH)"
                )

            def montar_where(filtros_extra=None):
                filtros = list(filtros_base)
                if filtros_extra:
                    filtros.extend(filtros_extra)
                return "WHERE " + " AND ".join(filtros) if filtros else ""

            # ======================= VISITANTES =======================

            # INÍCIO
            where_inicio = montar_where(["f.descricao = 'INICIO'"])
            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {where_inicio};
            """)
            inicio = fetch_one_dict(cursor)

            # GÊNERO
            where_genero = montar_where()
            cursor.execute(f"""
                SELECT 
                    SUM(v.genero='masculino') AS homens,
                    SUM(v.genero='feminino') AS mulheres,
                    COUNT(*) AS total
                FROM visitantes v
                {where_genero};
            """)
            genero = fetch_one_dict(cursor)

            # DISCIPULADO
            where_discipulado = montar_where(["f.descricao LIKE '%DISCIPULADO%'"])
            cursor.execute(f"""
                SELECT COUNT(DISTINCT v.id) AS total_discipulado
                FROM visitantes v
                JOIN status s ON v.id = s.visitante_id
                JOIN fases f ON s.fase_id = f.id
                {where_discipulado};
            """)
            discipulado = fetch_one_dict(cursor)

            # ORAÇÃO
            where_oracao = montar_where(["v.pedido_oracao IS NOT NULL"])
            cursor.execute(f"""
                SELECT COUNT(*) AS total_pedidos
                FROM visitantes v
                {where_oracao};
            """)
            oracao = fetch_one_dict(cursor)

            # ORIGEM
            cursor.execute(f"""
                SELECT COALESCE(v.indicacao, 'SEM INDICAÇÃO') AS origem,
                       COUNT(v.id) AS total
                FROM visitantes v
                {where_genero}
                GROUP BY v.indicacao
                ORDER BY total DESC;
            """)
            origem = fetch_all_dict(cursor)

            # MENSAL
            cursor.execute(f"""
                SELECT DATE_FORMAT(v.data_cadastro, '%Y-%m') AS mes,
                       COUNT(v.id) AS total
                FROM visitantes v
                {where_genero}
                GROUP BY mes
                ORDER BY mes DESC;
            """)
            mensal = fetch_all_dict(cursor)

            # CONVERSAS
            cursor.execute("""
                SELECT 
                    SUM(tipo='enviada') AS enviadas,
                    SUM(tipo='recebida') AS recebidas
                FROM conversas;
            """)
            conversas = fetch_one_dict(cursor)

            # FASES
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

            # DEMOGRAFIA
            cursor.execute(f"""
                SELECT 
                    ROUND(AVG(TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE())), 1) AS idade_media,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 12 AND 17 THEN 1 ELSE 0 END) AS adolescentes,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 18 AND 29 THEN 1 ELSE 0 END) AS jovens,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) BETWEEN 30 AND 59 THEN 1 ELSE 0 END) AS adultos,
                    SUM(CASE WHEN TIMESTAMPDIFF(YEAR, v.data_nascimento, CURDATE()) >= 60 THEN 1 ELSE 0 END) AS idosos
                FROM visitantes v
                {where_genero};
            """)
            idade = fetch_one_dict(cursor)

            cursor.execute(f"""
                SELECT 
                    COALESCE(v.estado_civil, 'Não Informado') AS estado_civil,
                    COUNT(*) AS total
                FROM visitantes v
                {where_genero}
                GROUP BY v.estado_civil
                ORDER BY total DESC
                LIMIT 10;
            """)
            estado_civil = fetch_all_dict(cursor)

            cursor.execute(f"""
                SELECT 
                    COALESCE(v.cidade, 'Não Informada') AS cidade,
                    COUNT(*) AS total
                FROM visitantes v
                {where_genero}
                GROUP BY v.cidade
                ORDER BY total DESC
                LIMIT 10;
            """)
            cidades = fetch_all_dict(cursor)

            # ======================= MEMBROS =======================

            cursor.execute("SELECT COUNT(*) AS total FROM membros;")
            membros_total = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT
                    SUM(genero='masculino') AS homens,
                    SUM(genero='feminino') AS mulheres,
                    COUNT(*) AS total
                FROM membros;
            """)
            membros_genero = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT
                    COALESCE(estado_civil, 'Não Informado') AS estado_civil,
                    COUNT(*) AS total
                FROM membros
                GROUP BY estado_civil
                ORDER BY total DESC;
            """)
            membros_estado_civil = fetch_all_dict(cursor)

            cursor.execute("""
                SELECT
                    SUM(novo_comeco = 1) AS fizeram,
                    SUM(novo_comeco = 0) AS nao_fizeram
                FROM membros;
            """)
            membros_novo_comeco = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT
                    SUM(classe_membros = 1) AS fizeram,
                    SUM(classe_membros = 0) AS nao_fizeram
                FROM membros;
            """)
            membros_classe = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT
                    SUM(consagracao = 1) AS consagrados,
                    SUM(consagracao = 0) AS nao_consagrados
                FROM membros;
            """)
            membros_consagracao = fetch_one_dict(cursor)

            cursor.execute("""
                SELECT
                    DATE_FORMAT(data_cadastro, '%Y-%m') AS mes,
                    COUNT(*) AS total
                FROM membros
                GROUP BY mes
                ORDER BY mes DESC;
            """)
            membros_mensal = fetch_all_dict(cursor)

            cursor.execute("""
                SELECT
                    COALESCE(cidade, 'Não Informada') AS cidade,
                    COUNT(*) AS total
                FROM membros
                GROUP BY cidade
                ORDER BY total DESC
                LIMIT 10;
            """)
            membros_cidades = fetch_all_dict(cursor)

            cursor.close()
            conn.close()

            return jsonify({
                "visitantes": {
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
                },
                "membros": {
                    "total": membros_total,
                    "genero": membros_genero,
                    "estado_civil": membros_estado_civil,
                    "novo_comeco": membros_novo_comeco,
                    "classe": membros_classe,
                    "consagracao": membros_consagracao,
                    "mensal": membros_mensal,
                    "cidades": membros_cidades
                }
            }), 200

        except Exception as e:
            logging.exception(e)
            return jsonify({"error": str(e)}), 500
