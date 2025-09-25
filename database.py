import pymysql
import pymysql.cursors
from contextlib import closing
import logging
from datetime import datetime
from typing import Optional, Dict

# =======================
# Função de Conexão com o Banco de Dados MySQL
# =======================

def get_db_connection():
    """Função para obter a conexão com o banco de dados MySQL"""
    try:
        conn = pymysql.connect(
            host='108.167.132.58',
            user='noust785_admin',
            password='M@st3rk3y',
            db='noust785_crm_mdc_canasvieiras',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao conectar ao banco de dados MySQL: {e}")
        raise

# =======================
# Funções de Visitantes
# =======================

def salvar_visitante(nome, telefone, email, data_nascimento, cidade, genero,
                     estado_civil, igreja_atual, frequenta_igreja, indicacao,
                     membro, pedido_oracao, horario_contato):
    """Salva um visitante no banco de dados."""
    try:
        # Verifica se o visitante já existe antes de tentar salvar
        if visitante_existe(telefone):
            logging.error(f"Erro: O telefone {telefone} já está cadastrado.")
            return False

        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Tenta inserir o visitante
            cursor.execute(''' 
                INSERT INTO visitantes (nome, telefone, email, data_nascimento,
                 cidade, genero, estado_civil, igreja_atual,
                 frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (nome, telefone, email, data_nascimento, cidade, genero, estado_civil,
                  igreja_atual, frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato))

            conn.commit()
            logging.info(f"Visitante {nome} cadastrado com sucesso com o telefone {telefone}!")
        return True

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao salvar visitante: {e}")
        return False

def salvar_membro(nome, telefone, email, data_nascimento, cep, bairro, cidade, estado, status_membro='ativo'):
    """Salva um membro no banco de dados."""
    try:
        # Verifica se o membro já existe antes de tentar salvar
        if membro_existe(telefone):
            logging.error(f"Erro: O telefone {telefone} já está cadastrado.")
            return False

        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Tenta inserir o membro
            cursor.execute(''' 
                INSERT INTO membros (nome, telefone, email, data_nascimento, cep, bairro, cidade, estado, status_membro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (nome, telefone, email, data_nascimento, cep, bairro, cidade, estado, status_membro))

            conn.commit()
            logging.info(f"Membro {nome} cadastrado com sucesso com o telefone {telefone}!")
        return True

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao salvar membro: {e}")
        return False

def membro_existe(telefone):
    """Verifica se um membro com o telefone fornecido já existe no banco de dados."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id_membro FROM membros WHERE telefone = %s", (telefone,))
            membro = cursor.fetchone()
            return membro is not None

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao verificar existência do membro: {e}")
        return False

def salvar_novo_visitante(telefone, nome):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO visitantes (nome, telefone, data_cadastro) 
                VALUES (%s, %s, NOW())
            ''', (nome, telefone))
            conn.commit()
            logging.info(f"Novo visitante {nome} registrado com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao registrar novo visitante: {e}")

def buscar_numeros_telefone():
    """Busca os números de telefone dos visitantes no banco de dados"""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT telefone FROM visitantes;')
            telefones = cursor.fetchall()
            return [row['telefone'] for row in telefones]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar números de telefone: {e}")
        return []

def visitante_existe(telefone):
    """Verifica se um visitante com o telefone especificado já existe."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM visitantes '
                           'WHERE telefone = %s;', (telefone,))
            result = cursor.fetchone()
            if result is None or 'count' not in result:
                return False
            return result['count'] > 0
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao verificar visitante: {e}")
        return False

# =======================
# Função de Atualização de Status
# =======================

def atualizar_status(telefone, nova_fase):
    """Atualiza o status de um visitante no banco de dados."""
    try:
        logging.info(f"Atualizando status para {nova_fase} para o número {telefone} no banco de dados.")
        fase_id = buscar_fase_id(nova_fase)
        if not fase_id:
            raise ValueError(f"Fase '{nova_fase}' não encontrada no banco de dados.")

        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            # Verifica se o status já existe para o visitante
            cursor.execute('''
                UPDATE status SET fase_id = %s
                WHERE visitante_id = (SELECT id FROM visitantes WHERE telefone = %s)
            ''', (fase_id, telefone))

            # Se o status não foi atualizado, insere um novo status
            if cursor.rowcount == 0:
                cursor.execute('''
                    INSERT INTO status (visitante_id, fase_id)
                    VALUES ((SELECT id FROM visitantes WHERE telefone = %s), %s)
                ''', (telefone, fase_id))

            conn.commit()
            logging.info(f"Status atualizado para fase '{nova_fase}' (id {fase_id}) para o telefone {telefone}")

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao atualizar status para o telefone {telefone}: {e}")

# =======================
# Funções de Estatísticas e Conversas
# =======================

def salvar_estatistica(numero, estado_atual, proximo_estado):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO estatisticas (numero, estado_atual, proximo_estado, data_hora)
                VALUES (%s, %s, %s, %s)
            ''', (numero, estado_atual, proximo_estado, datetime.now()))
            conn.commit()
            logging.info(f"Estatística salva para o número {numero} "
                         f"com estado atual {estado_atual} e "
                         f"próximo estado {proximo_estado}.")
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao salvar estatística para {numero}: {e}")

def salvar_conversa(numero, mensagem, tipo='recebida', sid=None):
    """Salva a conversa de um visitante no banco de dados, incluindo o SID da mensagem."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversas (visitante_id, mensagem, tipo, message_sid)
                VALUES ((SELECT id FROM visitantes WHERE telefone = %s), %s, %s, %s)
            ''', (numero, mensagem, tipo, sid))
            conn.commit()
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao salvar conversa para o telefone {numero}. Detalhes: {e}")

def monitorar_status_visitantes():
    """Retorna o status de todos os visitantes cadastrados, excluindo a fase ID 11 (Importados)."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.id, v.nome, v.telefone, COALESCE(f.descricao, 'Cadastrado') AS fase_atual
                FROM visitantes v 
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                WHERE f.id != 11 OR f.id IS NULL;
            ''')
            rows = cursor.fetchall()

            if not rows:
                logging.error("Nenhum status encontrado para os visitantes.")
                return []

            status_info = []
            for row in rows:
                status_info.append({
                    'id': row['id'],
                    'name': row['nome'],
                    'phone': row['telefone'],
                    'status': row['fase_atual'] if row['fase_atual'] else 'Cadastrado'
                })

            logging.info(f"Status de {len(status_info)} visitantes monitorados com sucesso.")
            return status_info

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar status de visitantes no banco de dados: {e}")
        return None

def registrar_estatistica(numero, estado_atual, proximo_estado):
    try:
        salvar_estatistica(numero, estado_atual, proximo_estado)
        logging.info(f"Estatística registrada para {numero}: Estado atual: {estado_atual}, "
                     f"Próximo estado: {proximo_estado}")
    except Exception as e:
        logging.error(f"Erro ao salvar a estatística para {numero}: {e}")

def buscar_fase_id(descricao_fase):
    """Busca o ID de uma fase com base na sua descrição."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM fases WHERE descricao = %s', (descricao_fase,))
            fase = cursor.fetchone()
            return fase['id'] if fase else None
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar fase: {e}")
        return None

def obter_dados_visitante(telefone: str) -> Optional[Dict]:
    query = """
        SELECT nome, email, data_nascimento, cidade, genero, estado_civil 
        FROM visitantes 
        WHERE telefone = %s
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (telefone,))
                resultado = cursor.fetchone()
                return resultado if resultado else None
    except Exception as e:
        logging.error(f"Erro ao buscar dados do visitante: {e}")
        return None

def obter_nome_do_visitante(telefone: str) -> str:
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            telefone_normalizado = normalizar_para_recebimento(telefone)

            cursor.execute('''
                SELECT nome FROM visitantes WHERE telefone = %s LIMIT 1
            ''', (telefone_normalizado,))

            resultado = cursor.fetchone()

            if resultado:
                return resultado['nome']
            else:
                logging.warning(f"Visitante com telefone {telefone} não encontrado.")
                return 'Visitante não Cadastrado'

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar nome do visitante: {e}")
        return 'Sem dados!'

# =======================
# Funções de Conversas
# =======================

def obter_estado_atual_do_banco(telefone):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COALESCE(f.descricao, 'INICIO') AS fase_atual
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                WHERE v.telefone = %s
            ''', (telefone,))

            resultado = cursor.fetchone()

            if resultado and resultado['fase_atual']:
                return resultado['fase_atual']
            else:
                return 'INICIO'

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao obter estado do visitante {telefone}: {e}")
        return 'INICIO'

def mensagem_sid_existe(message_sid: str) -> bool:
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM conversas WHERE message_sid = %s', (message_sid,))
            count = cursor.fetchone()[0]
            return count > 0
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao verificar SID da mensagem: {e}")
        return False

def salvar_pedido_oracao(telefone, pedido):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE visitantes 
                SET pedido_oracao = %s 
                WHERE telefone = %s
            ''', (pedido, telefone))

            conn.commit()
            logging.info(f"Pedido de oração salvo para o visitante com telefone {telefone}.")
            return True

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao salvar pedido de oração: {e}")
        return False

def atualizar_dado_visitante(numero, campo, valor):
    query = f"UPDATE visitantes SET {campo} = %s WHERE telefone = %s"

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (valor, numero))
            conn.commit()

# =======================
# Funções Auxiliares de Normalização
# =======================

def normalizar_para_envio(telefone: str) -> str:
    telefone = ''.join(filter(lambda x: x.isdigit(), telefone))

    if len(telefone) < 10:
        raise ValueError(f"Telefone inválido: {telefone}. Número deve ter ao menos 10 dígitos.")

    if telefone.startswith('55'):
        telefone = telefone[2:]

    ddd, numero = telefone[:2], telefone[2:]

    if len(numero) == 9 and numero[0] == '9':
        numero = numero[1:]

    return f"55{ddd}{numero}"

def normalizar_para_recebimento(telefone: str) -> str:
    logging.info(f"Recebendo telefone para normalização: {telefone}")

    if telefone.startswith('whatsapp:'):
        telefone = telefone.replace('whatsapp:', '')
        logging.info(f"Prefixo 'whatsapp:' removido, número agora é: {telefone}")

    telefone = ''.join(filter(lambda x: x.isdigit(), telefone))

    if telefone.startswith('55'):
        telefone = telefone[2:]

    ddd = telefone[:2]
    numero = telefone[2:]

    if len(numero) == 8:
        numero = '9' + numero

    if len(ddd) != 2 or len(numero) != 9:
        logging.error(f"Número de telefone inválido após normalização: {telefone}")
        raise ValueError(f"Número de telefone inválido: {telefone}")

    telefone_normalizado = f'{ddd}{numero}'
    logging.info(f"Número normalizado: {telefone_normalizado}")

    return telefone_normalizado

# =======================
# Funções de Status e Fases
# =======================

def visitantes_listar_fases():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(''' 
                SELECT v.nome, v.telefone, f.descricao AS fase_atual
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
            ''')
            return cursor.fetchall()
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar fases dos visitantes: {e}")
        return {"error": "Erro ao listar fases."}

def visitantes_listar_estatisticas():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM estatisticas")
            return cursor.fetchall()
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar estatísticas: {e}")
        return {"error": "Erro ao listar estatísticas."}

def visitantes_monitorar_status():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.nome, v.telefone, f.descricao AS fase_atual
                FROM visitantes v 
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
            ''')
            return cursor.fetchall()
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar status de visitantes no banco de dados: {e}")
        return None

def listar_todos_visitantes():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT v.id AS visitante_id, v.nome, v.telefone, v.email, v.data_nascimento, v.cidade, 
                       v.genero, v.estado_civil, v.igreja_atual, v.frequenta_igreja, v.indicacao, 
                       v.membro, v.pedido_oracao, v.horario_contato,
                       COALESCE(f.descricao, 'Cadastrado') AS fase,
                       i.tipo AS interacao_tipo, i.data_hora AS interacao_data, i.observacao AS interacao_observacao
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                LEFT JOIN interacoes i ON v.id = i.visitante_id
            ''')

            visitantes = cursor.fetchall()

            if visitantes:
                colunas = [desc[0] for desc in cursor.description]
                visitantes_list = [dict(zip(colunas, visitante)) for visitante in visitantes]
                return visitantes_list

            return []

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar visitantes no banco de dados: {e}")
        return {"error": "Erro ao listar visitantes."}

def listar_visitantes_fase_null():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT v.id, v.nome, v.telefone 
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                WHERE s.fase_id IS NULL
            ''')

            visitantes = cursor.fetchall()

            if visitantes:
                visitantes_list = [{"id": row["id"], "name": row["nome"],
                                    "phone": row["telefone"]} for row in visitantes]
                return visitantes_list

            return []

    except pymysql.MySQLError as e:
        logging.error(f"Erro ao listar visitantes com fase NULL: {e}")
        return {"error": "Erro ao listar visitantes com fase NULL"}

# =======================
# Funções de Contagem e Estatísticas
# =======================

def visitantes_contar_novos():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM visitantes WHERE data_nascimento IS NOT NULL")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar novos visitantes: {e}")
        return 0

def visitantes_contar_membros_interessados():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM status WHERE fase_id = "
                           "(SELECT id FROM fases WHERE descricao = 'INTERESSE_DISCIPULADO')")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar membros interessados: {e}")
        return 0

def visitantes_contar_sem_retorno():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM visitantes WHERE horario_contato IS NULL")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar visitantes sem retorno: {e}")
        return 0

def visitantes_contar_discipulado_enviado():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM status WHERE fase_id ="
                           " (SELECT id FROM fases WHERE descricao = 'INTERESSE_DISCIPULADO')")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar visitantes enviados ao discipulado: {e}")
        return 0

def visitantes_contar_sem_interesse_discipulado():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM status WHERE fase_id = "
                           "(SELECT id FROM fases WHERE descricao = 'INTERESSE_NOVO_COMEC')")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar visitantes sem interesse no discipulado: {e}")
        return 0

def visitantes_contar_sem_retorno_total():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM status WHERE fase_id IS NULL")
            return cursor.fetchone()[0]
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao contar visitantes sem retorno total: {e}")
        return 0

def obter_conversa_por_visitante(visitante_id):
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()

            consulta_sql = """
            SELECT 
                CASE 
                    WHEN c.tipo = 'enviada' THEN 'Bot'
                    ELSE v.nome
                END AS remetente,
                c.mensagem,  
                c.data_hora 
            FROM conversas c
            INNER JOIN visitantes v ON v.id = c.visitante_id
            WHERE c.visitante_id = %s
            ORDER BY c.data_hora;
            """

            cursor.execute(consulta_sql, (visitante_id,))
            conversas = cursor.fetchall()

            resultado = "<div class='chat-conversa'>"
            for conversa in conversas:
                resultado += (f"<p><strong>{conversa['remetente']}:</strong>"
                              f" {conversa['mensagem']} <br><small>{conversa['data_hora']}</small></p>")
            resultado += "</div>"

            return resultado
    except pymysql.MySQLError as e:
        logging.error(f"Erro ao buscar conversa para o visitante {visitante_id}: {e}")
        return "<p>Erro ao obter conversa.</p>"

def obter_total_visitantes():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            logging.info("Iniciando a consulta para o total de visitantes com telefone registrado...")
            cursor.execute("SELECT COUNT(*) FROM visitantes")
            result = cursor.fetchone()

            logging.debug(f"Resultado de fetchone(): {result}")

            if result:
                total_visitantes_com_telefone = result['COUNT(*)']
                logging.info(f"Total de visitantes com telefone registrado: {total_visitantes_com_telefone}")
            else:
                total_visitantes_com_telefone = 0
                logging.warning("Nenhum visitante com telefone encontrado, retornando 0.")

            return formatar_com_pontos(total_visitantes_com_telefone)

    except Exception as e:
        logging.error(f"Erro ao obter total de visitantes com telefone: {e}")
        return 0

def obter_total_membros():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            logging.info("Iniciando a consulta para o total de membros...")

            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_membros,
                    SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) AS total_homensmembro,
                    SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) AS total_mulheresmembro
                FROM membros
            """)
            result = cursor.fetchone()

            logging.debug(f"Resultado de fetchone(): {result}")

            if result:
                total_membros = result['total_membros'] or 0
                total_homensmembro = result['total_homensmembro'] or 0
                total_mulheresmembro = result['total_mulheresmembro'] or 0
                logging.info(f"Total de membros: {total_membros}, Homens: {total_homensmembro},"
                             f" Mulheres: {total_mulheresmembro}")
            else:
                total_membros = total_homensmembro = total_mulheresmembro = 0
                logging.warning("Nenhum membro encontrado, retornando 0.")

            return total_membros, total_homensmembro, total_mulheresmembro

    except Exception as e:
        logging.error(f"Erro ao obter total de membros: {e}")
        return 0, 0, 0

def obter_total_discipulados():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            logging.info("Iniciando a consulta para total de discipulados...")

            cursor.execute("""
                SELECT 
                    (
                        (SELECT COUNT(DISTINCT v.telefone) 
                         FROM conversas c
                         INNER JOIN visitantes v ON v.id = c.visitante_id
                         WHERE c.mensagem LIKE '%Discipulado%'
                        )
                        +
                        (SELECT COUNT(DISTINCT telefone) 
                         FROM visitantes
                         WHERE membro = 1
                        )
                    ) AS total_discipulado,

                    (
                        (SELECT COUNT(DISTINCT v.telefone) 
                         FROM conversas c
                         INNER JOIN visitantes v ON v.id = c.visitante_id
                         WHERE c.mensagem LIKE '%Discipulado%' AND v.genero = 'masculino'
                        )
                        +
                        (SELECT COUNT(DISTINCT telefone) 
                         FROM visitantes
                         WHERE membro = 1 AND genero = 'masculino'
                        )
                    ) AS total_homens,

                    (
                        (SELECT COUNT(DISTINCT v.telefone) 
                         FROM conversas c
                         INNER JOIN visitantes v ON v.id = c.visitante_id
                         WHERE c.mensagem LIKE '%Discipulado%' AND v.genero = 'feminino'
                        )
                        +
                        (SELECT COUNT(DISTINCT telefone) 
                         FROM visitantes
                         WHERE membro = 1 AND genero = 'feminino'
                        )
                    ) AS total_mulheres
            """)
            result = cursor.fetchone()

            logging.debug(f"Resultado de fetchone(): {result}")

            total_discipulado = result['total_discipulado'] if result else 0
            total_homens = result['total_homens'] if result else 0
            total_mulheres = result['total_mulheres'] if result else 0

            logging.info(f"Total discipulado: {total_discipulado}, Total Homens: {total_homens}, "
                         f"Total Mulheres: {total_mulheres}")

            return total_discipulado, total_homens, total_mulheres

    except Exception as e:
        logging.error(f"Erro ao obter total de discipulados: {e}")
        return 0, 0, 0

def obter_dados_genero():
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            logging.info("Iniciando a consulta para dados de gênero...")

            cursor.execute("""
                           SELECT 
                               SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) AS Homens,
                               ROUND(SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) 
                               AS Homens_Percentual,
                               SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) AS Mulheres,
                               ROUND(SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) 
                               AS Mulheres_Percentual
                           FROM visitantes;
                       """)

            result = cursor.fetchone()
            logging.debug(f"Resultado de fetchone(): {result}")

            if result:
                dados_genero = {
                    "Homens": int(result['Homens']) if result['Homens'] else 0,
                    "Homens_Percentual": int(result['Homens_Percentual']) if result['Homens_Percentual'] else 0,
                    "Mulheres": int(result['Mulheres']) if result['Mulheres'] else 0,
                    "Mulheres_Percentual": int(result['Mulheres_Percentual']) if result['Mulheres_Percentual'] else 0
                }
                logging.info(f"Dados de gênero obtidos: {dados_genero}")
            else:
                dados_genero = {
                    "Homens": 0,
                    "Homens_Percentual": 0,
                    "Mulheres": 0,
                    "Mulheres_Percentual": 0
                }
                logging.warning("Nenhum dado de gênero encontrado, retornando valores padrão.")

            return dados_genero

    except Exception as e:
        logging.error(f"Erro ao obter dados de gênero: {str(e)}")
        return {
            "Homens": 0,
            "Homens_Percentual": 0,
            "Mulheres": 0,
            "Mulheres_Percentual": 0
        }

def formatar_com_pontos(numero):
    """Formata o número com ponto como separador de milhar."""
    return "{:,.0f}".format(numero).replace(',', '.')

# --- NOVAS FUNÇÕES PARA TREINAMENTO DA IA ---

def salvar_par_treinamento(pergunta: str, resposta: str, categoria: str = 'geral', fonte: str = 'manual'):
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO training_pairs (question, answer, category, fonte, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE answer = VALUES(answer), updated_at = NOW()
        """, (pergunta, resposta, categoria, fonte))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar par de treinamento: {e}")
        return False

def obter_pares_treinamento():
    """
    CORREÇÃO: Removido dictionary=True - PyMySQL já retorna dicionários
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()  # CORREÇÃO APLICADA
        cursor.execute("""
            SELECT question, answer FROM training_pairs 
            ORDER BY id DESC LIMIT 1000
        """)
        pares = cursor.fetchall()
        cursor.close()
        conn.close()
        return pares
    except Exception as e:
        logging.error(f"Erro ao obter pares de treinamento: {e}")
        return []

def obter_perguntas_pendentes():
    """
    CORREÇÃO: Removido dictionary=True - PyMySQL já retorna dicionários
    """
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()  # CORREÇÃO APLICADA
        cursor.execute("""
            SELECT id, user_id, question, created_at FROM unknown_questions 
            WHERE status = 'pending' ORDER BY created_at DESC LIMIT 50
        """)
        perguntas = cursor.fetchall()
        cursor.close()
        conn.close()
        return perguntas
    except Exception as e:
        logging.error(f"Erro ao obter perguntas pendentes: {e}")
        return []

def marcar_pergunta_como_respondida(pergunta: str):
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute("UPDATE unknown_questions SET status = 'answered' WHERE question = %s", (pergunta,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Erro ao marcar pergunta como respondida: {e}")
        return False
