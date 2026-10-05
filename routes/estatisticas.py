import logging
from flask import jsonify, request
from database import get_db_connection


def _rows(cursor):
    rows = cursor.fetchall() or []
    if rows and isinstance(rows[0], dict):
        return rows
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def _one(cursor):
    row = cursor.fetchone()
    if not row:
        return {}
    if isinstance(row, dict):
        return row
    return dict(zip([c[0] for c in cursor.description], row))


def _periodo():
    try:
        meses = int(request.args.get('meses', 6))
    except (TypeError, ValueError):
        meses = 6
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

            cursor.execute(f"SELECT COUNT(*) total FROM visitantes v {filtro_v}"); total = _one(cursor).get('total', 0)
            cursor.execute(f"SELECT SUM(LOWER(COALESCE(v.genero,''))='masculino') homens,SUM(LOWER(COALESCE(v.genero,''))='feminino') mulheres FROM visitantes v {filtro_v}"); genero=_one(cursor)
            cursor.execute(f"SELECT COUNT(*) total_pedidos FROM visitantes v {filtro_v} {'AND' if filtro_v else 'WHERE'} NULLIF(TRIM(COALESCE(v.pedido_oracao,'')),'') IS NOT NULL"); oracao=_one(cursor)
            cursor.execute(f"SELECT COUNT(DISTINCT v.id) total_discipulado FROM visitantes v JOIN status s ON s.visitante_id=v.id JOIN fases f ON f.id=s.fase_id WHERE UPPER(f.descricao) LIKE '%DISCIPULADO%' {and_v}"); discipulado=_one(cursor)
            cursor.execute(f"SELECT COUNT(DISTINCT v.id) total_interesse_membro FROM visitantes v LEFT JOIN status s ON s.visitante_id=v.id LEFT JOIN fases f ON f.id=s.fase_id WHERE (LOWER(COALESCE(v.membro,'')) IN ('sim','s','1','true') OR UPPER(COALESCE(f.descricao,'')) LIKE '%MEMBR%') {and_v}"); interesse=_one(cursor)

            cursor.execute(f"SELECT DATE_FORMAT(v.data_cadastro,'%Y-%m') mes,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY mes ORDER BY mes"); mensal=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.indicacao),''),'Não informado') origem,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY origem ORDER BY total DESC LIMIT 10"); origem=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.cidade),''),'Não informada') cidade,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY cidade ORDER BY total DESC LIMIT 10"); cidades=_rows(cursor)
            cursor.execute(f"SELECT COALESCE(NULLIF(TRIM(v.estado_civil),''),'Não informado') estado_civil,COUNT(*) total FROM visitantes v {filtro_v} GROUP BY estado_civil ORDER BY total DESC LIMIT 10"); estado_civil=_rows(cursor)
            cursor.execute(f"SELECT ROUND(AVG(TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE())),1) idade_media,SUM(TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 12 AND 17) adolescentes,SUM(TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 18 AND 29) jovens,SUM(TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) BETWEEN 30 AND 59) adultos,SUM(TIMESTAMPDIFF(YEAR,v.data_nascimento,CURDATE()) >= 60) idosos FROM visitantes v {filtro_v}"); idade=_one(cursor)

            cursor.execute(f"SELECT SUM(LOWER(c.tipo)='enviada') enviadas,SUM(LOWER(c.tipo)='recebida') recebidas,COUNT(*) total,COUNT(DISTINCT c.visitante_id) pessoas FROM conversas c {filtro_c}"); conversas=_one(cursor)
            cursor.execute(f"SELECT COUNT(DISTINCT c.visitante_id) responderam FROM conversas c {'JOIN visitantes v ON v.id=c.visitante_id ' + filtro_v if filtro_v else ''} WHERE LOWER(c.tipo)='recebida'" if not filtro_v else f"SELECT COUNT(DISTINCT c.visitante_id) responderam FROM conversas c JOIN visitantes v ON v.id=c.visitante_id WHERE LOWER(c.tipo)='recebida' {and_v}"); responderam=_one(cursor)

            cursor.execute(f"SELECT COALESCE(f.descricao,'SEM FASE') fase,COUNT(DISTINCT v.id) total FROM visitantes v LEFT JOIN status s ON s.visitante_id=v.id LEFT JOIN fases f ON f.id=s.fase_id {filtro_v} GROUP BY f.descricao ORDER BY total DESC"); fases=_rows(cursor)

            # Funil baseado somente em evidências estruturadas disponíveis.
            contatados = int(conversas.get('pessoas') or 0)
            interagiram = int(responderam.get('responderam') or 0)
            funil = [
                {'etapa':'Visitantes','total':int(total or 0)},
                {'etapa':'Contatados','total':contatados},
                {'etapa':'Interagiram','total':interagiram},
                {'etapa':'Desejam ser membro','total':int(interesse.get('total_interesse_membro') or 0)},
                {'etapa':'Discipulado','total':int(discipulado.get('total_discipulado') or 0)}
            ]
            def taxa(n,d): return round((n/d*100),1) if d else 0
            indicadores = {
                'taxa_contato': taxa(contatados,total), 'taxa_interacao': taxa(interagiram,contatados),
                'taxa_discipulado': taxa(int(discipulado.get('total_discipulado') or 0),total),
                'taxa_interesse_membro': taxa(int(interesse.get('total_interesse_membro') or 0),total)
            }

            # Membros: preserva indicadores existentes.
            cursor.execute("SELECT COUNT(*) total FROM membros"); membros_total=_one(cursor)
            cursor.execute("SELECT SUM(LOWER(COALESCE(genero,''))='masculino') homens,SUM(LOWER(COALESCE(genero,''))='feminino') mulheres FROM membros"); membros_genero=_one(cursor)

            return jsonify({'periodo_meses':meses,'visitantes':{
                'total':int(total or 0),'genero':genero,'discipulado':discipulado,'oracao':oracao,'interesse_membro':interesse,
                'mensal':mensal,'origem':origem,'conversas':conversas,'fases':fases,
                'demografia':{'idade':idade,'estado_civil':estado_civil,'cidades':cidades},
                'funil':funil,'indicadores':indicadores
            },'membros':{'total':membros_total,'genero':membros_genero}}),200
        except Exception as e:
            logging.exception('Erro em estatisticas/geral')
            return jsonify({'error':str(e)}),500
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
