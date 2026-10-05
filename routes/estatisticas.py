import logging
from flask import jsonify, request
from database import get_db_connection


def _rows(cursor):
    rows = cursor.fetchall() or []
    if rows and isinstance(rows[0], dict): return rows
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def _one(cursor):
    row = cursor.fetchone()
    if not row: return {}
    if isinstance(row, dict): return row
    return dict(zip([c[0] for c in cursor.description], row))


def _periodo():
    try: meses = int(request.args.get('meses', 6))
    except (TypeError, ValueError): meses = 6
    return max(0, min(meses, 120))


def register(app):
    @app.route('/api/estatisticas/geral', methods=['GET'])
    def estatisticas_geral():
        conn = cursor = None
        try:
            meses = _periodo()
            conn = get_db_connection(); cursor = conn.cursor()
            filtro_v = "" if meses == 0 else f"WHERE v.data_cadastro >= DATE_SUB(CURDATE(), INTERVAL {meses} MONTH)"
            and_v = "" if meses == 0 else f"AND v.data_cadastro >= DATE_SUB(CURDATE(), INTERVAL {meses} MONTH)"
            filtro_c = "" if meses == 0 else f"WHERE c.data_hora >= DATE_SUB(NOW(), INTERVAL {meses} MONTH)"

            # STATUS/FASES representa o estado conversacional do Integra+.
            status_atual = """
                SELECT s.visitante_id, s.fase_id
                FROM status s
                INNER JOIN (
                    SELECT visitante_id, MAX(id) AS max_id
                    FROM status
                    GROUP BY visitante_id
                ) ult ON ult.max_id = s.id
            """

            cursor.execute(f"SELECT COUNT(*) total FROM visitantes v {filtro_v}"); total_i = int(_one(cursor).get('total') or 0)
            cursor.execute(f"SELECT SUM(LOWER(TRIM(COALESCE(v.genero,''))) IN ('masculino','m')) homens,SUM(LOWER(TRIM(COALESCE(v.genero,''))) IN ('feminino','f')) mulheres FROM visitantes v {filtro_v}"); genero=_one(cursor)
            cursor.execute(f"SELECT COUNT(*) total_pedidos FROM visitantes v {filtro_v} {'AND' if filtro_v else 'WHERE'} NULLIF(TRIM(COALESCE(v.pedido_oracao,'')),'') IS NOT NULL"); oracao=_one(cursor)
            cursor.execute(f"SELECT COUNT(*) total_interesse_membro FROM visitantes v {filtro_v} {'AND' if filtro_v else 'WHERE'} LOWER(TRIM(COALESCE(v.membro,''))) IN ('sim','s','1','true')"); interesse=_one(cursor)

            cursor.execute(f"SELECT DATE_FORMAT(v.data_cadastro,'%Y-%m') mes,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY mes ORDER BY mes"); mensal=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.indicacao),''),'Não informado') origem,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY origem ORDER BY total DESC LIMIT 10"); origem=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.cidade),''),'Não informada') cidade,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY cidade ORDER BY total DESC LIMIT 10"); cidades=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.estado_civil),''),'Não informado') estado_civil,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY estado_civil ORDER BY total DESC LIMIT 10"); estado_civil=_rows(cursor)
            cursor.execute(f"SELECT ROUND(AVG(CASE WHEN v.data_nascimento IS NOT NULL AND v.data_nascimento <= CURDATE() THEN TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) END),1) idade_media,SUM(v.data_nascimento IS NOT NULL AND TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 12 AND 17) adolescentes,SUM(v.data_nascimento IS NOT NULL AND TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 18 AND 29) jovens,SUM(v.data_nascimento IS NOT NULL AND TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 30 AND 59) adultos,SUM(v.data_nascimento IS NOT NULL AND TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) >= 60) idosos FROM visitantes v {filtro_v}"); idade=_one(cursor)

            # Atividade do Integra+ no período: mede mensagens ocorridas no período,
            # independentemente de quando o visitante foi cadastrado.
            cursor.execute(f"SELECT SUM(LOWER(TRIM(COALESCE(c.tipo,'')))='enviada') enviadas,SUM(LOWER(TRIM(COALESCE(c.tipo,'')))='recebida') recebidas,COUNT(*) total,COUNT(DISTINCT c.visitante_id) pessoas FROM conversas c {filtro_c}"); conversas=_one(cursor)

            # Jornada pastoral usa uma coorte de visitantes cadastrados no período.
            # Contato/resposta são procurados no histórico desses visitantes, evitando
            # misturar visitantes antigos na taxa e impedindo percentuais > 100%.
            cursor.execute(f"SELECT COUNT(DISTINCT v.id) contatados FROM visitantes v JOIN conversas c ON c.visitante_id=v.id {filtro_v}"); contatados_row=_one(cursor)
            cursor.execute(f"SELECT COUNT(DISTINCT v.id) responderam FROM visitantes v JOIN conversas c ON c.visitante_id=v.id {filtro_v} {'AND' if filtro_v else 'WHERE'} LOWER(TRIM(COALESCE(c.tipo,'')))='recebida'"); responderam=_one(cursor)

            cursor.execute(f"""
                SELECT COALESCE(f.descricao,'SEM FASE') fase, COUNT(*) total
                FROM visitantes v
                LEFT JOIN ({status_atual}) sa ON sa.visitante_id=v.id
                LEFT JOIN fases f ON f.id=sa.fase_id
                {filtro_v}
                GROUP BY f.id, f.descricao ORDER BY total DESC
            """); estados_bot=_rows(cursor)

            # Intenções registradas no histórico do bot para a coorte selecionada.
            # Cada visitante conta no máximo uma vez em cada intenção.
            cursor.execute(f"""
                SELECT f.descricao intencao, COUNT(DISTINCT v.id) total
                FROM visitantes v
                JOIN status s ON s.visitante_id=v.id
                JOIN fases f ON f.id=s.fase_id
                WHERE f.descricao IN (
                    'INTERESSE_DISCIPULADO','INTERESSE_NOVO_COMEC','PEDIDO_ORACAO',
                    'HORARIOS','LINK_WHATSAPP','OUTRO'
                ) {and_v}
                GROUP BY f.id, f.descricao ORDER BY total DESC
            """); intencoes_bot=_rows(cursor)

            interesse_discipulado = next((int(x.get('total') or 0) for x in intencoes_bot if x.get('intencao') == 'INTERESSE_DISCIPULADO'), 0)
            contatados = int(contatados_row.get('contatados') or 0)
            interagiram = int(responderam.get('responderam') or 0)
            interesse_i = int(interesse.get('total_interesse_membro') or 0)
            jornada = [
                {'etapa':'Visitantes','total':total_i,'fonte':'cadastro'},
                {'etapa':'Contatados','total':contatados,'fonte':'histórico de conversas da coorte'},
                {'etapa':'Interagiram','total':interagiram,'fonte':'mensagens recebidas da coorte'},
                {'etapa':'Interesse em membresia','total':interesse_i,'fonte':'visitantes.membro'}
            ]
            def taxa(n,d): return round((n/d*100),1) if d else 0
            indicadores = {
                'taxa_contato': taxa(contatados,total_i),
                'taxa_interacao': taxa(interagiram,contatados),
                'taxa_interesse_membro': taxa(interesse_i,total_i),
                'interesse_discipulado_bot': interesse_discipulado
            }

            cursor.execute(f"""
                SELECT
                    SUM(sa.visitante_id IS NULL OR sa.fase_id IS NULL) sem_fase,
                    SUM(sa.fase_id IS NOT NULL AND f.id IS NULL) fase_invalida,
                    SUM(sa.fase_id IS NOT NULL AND f.id IS NOT NULL) com_fase
                FROM visitantes v
                LEFT JOIN ({status_atual}) sa ON sa.visitante_id=v.id
                LEFT JOIN fases f ON f.id=sa.fase_id
                {filtro_v}
            """); qualidade_status=_one(cursor)

            cursor.execute("SELECT COUNT(*) total FROM membros"); membros_total=_one(cursor)
            cursor.execute("SELECT SUM(LOWER(TRIM(COALESCE(genero,''))) IN ('masculino','m')) homens,SUM(LOWER(TRIM(COALESCE(genero,''))) IN ('feminino','f')) mulheres FROM membros"); membros_genero=_one(cursor)

            return jsonify({'periodo_meses':meses,'visitantes':{
                'total':total_i,'genero':genero,'oracao':oracao,'interesse_membro':interesse,
                'mensal':mensal,'origem':origem,'conversas':conversas,
                'estados_bot':estados_bot,'intencoes_bot':intencoes_bot,'qualidade_status':qualidade_status,
                'demografia':{'idade':idade,'estado_civil':estado_civil,'cidades':cidades},
                'jornada':jornada,'indicadores':indicadores,
                'discipulado':{'estruturado':False,'interesse_bot':interesse_discipulado}
            },'membros':{'total':membros_total,'genero':membros_genero}}),200
        except Exception as e:
            logging.exception('Erro em estatisticas/geral')
            return jsonify({'error':str(e)}),500
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
