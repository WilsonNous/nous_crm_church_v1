# database.py — CRM Church (Integra+)
# Versão consolidada e corrigida (MySQL/PyMySQL + DictCursor)
# Will: copiar e colar inteiro ✅

import os
import logging
from datetime import datetime
from contextlib import closing
from typing import Optional, Dict

# =======================
# PyMySQL (com fallback)
# =======================
try:
    import pymysql
    HAVE_PYMYSQL = True
except Exception:
    pymysql = None
    HAVE_PYMYSQL = False

    class _DummyError(Exception):
        pass

    class _DummyPymysql:
        MySQLError = _DummyError

    pymysql = _DummyPymysql()


# =======================
# Conexão MySQL
# =======================
def get_db_connection():
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            db=os.getenv("MYSQL_DB"),
            port=int(os.getenv("MYSQL_PORT", 3306)),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,  # ✅ sempre dict
            autocommit=False
        )
        return conn
    except Exception as e:
        logging.error(f"❌ Erro ao conectar no MySQL: {e}")
        return None


# =======================
# Visitantes / Membros
# =======================
def salvar_visitante(nome, telefone, email, data_nascimento, cidade, genero,
                     estado_civil, igreja_atual, frequenta_igreja, indicacao,
                     membro, pedido_oracao, horario_contato, origem="integra+"):
    """Salva um visitante no banco de dados com origem."""
    try:
        if visitante_existe(telefone):
            logging.error(f"Erro: O telefone {telefone} já está cadastrado.")
            return False

        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO visitantes (
                    nome, telefone, email, data_nascimento,
                    cidade, genero, estado_civil, igreja_atual,
                    frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato, origem
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                nome, telefone, email, data_nascimento, cidade, genero, estado_civil,
                igreja_atual, frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato, origem
            ))
            conn.commit()

        logging.info(f"✅ Visitante {nome} cadastrado com sucesso com o telefone {telefone}!")
        return True

    except Exception as e:
        logging.error(f"Erro ao salvar visitante: {e}")
        return False


def salvar_membro(dados: dict):
    """
    Salva um membro com TODOS os dados coletados no formulário completo.
    'dados' deve vir como JSON enviado pelo front-end.
    """
    try:
        telefone = dados.get("telefone")

        if membro_existe(telefone):
            logging.error(f"❌ O telefone {telefone} já está cadastrado.")
            return False

        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()

            sql_membro = """
                INSERT INTO membros 
                (nome, telefone, email, data_nascimento, 
                 cep, bairro, cidade, estado,
                 estado_civil, conjuge_nome,
                 possui_filhos, filhos_info,
                 novo_comeco, novo_comeco_quando,
                 classe_membros, apresentacao_data,
                 consagracao, status_membro)
                VALUES (%s, %s, %s, %s, 
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s);
            """

            cursor.execute(sql_membro, (
                dados.get("nome"),
                telefone,
                dados.get("email"),
                dados.get("data_nascimento"),

                dados.get("cep"),
                dados.get("bairro"),
                dados.get("cidade"),
                dados.get("estado"),

                dados.get("estado_civil"),
                dados.get("conjuge_nome"),

                dados.get("possui_filhos"),
                dados.get("filhos_info"),

                dados.get("novo_comeco"),
                dados.get("novo_comeco_quando"),

                dados.get("classe_membros"),
                dados.get("apresentacao_data"),

                dados.get("consagracao"),
                dados.get("status_membro", "ativo")
            ))

            id_membro = cursor.lastrowid

            discipulados = dados.get("discipulados", [])
            if discipulados:
                for item in discipulados:
                    cursor.execute("""
                        INSERT INTO membros_discipulados (id_membro, discipulado)
                        VALUES (%s, %s)
                    """, (id_membro, item))

            ministerios = dados.get("ministerios", [])
            if ministerios:
                for item in ministerios:
                    cursor.execute("""
                        INSERT INTO membros_ministerios (id_membro, ministerio)
                        VALUES (%s, %s)
                    """, (id_membro, item))

            if dados.get("ministerios_outros"):
                cursor.execute("""
                    INSERT INTO membros_ministerios (id_membro, ministerio)
                    VALUES (%s, %s)
                """, (id_membro, dados.get("ministerios_outros")))

            conn.commit()
            logging.info(f"🟢 Membro '{dados.get('nome')}' (#ID {id_membro}) cadastrado com sucesso!")
            return True

    except Exception as e:
        logging.error(f"❌ Erro ao salvar membro completo: {e}")
        return False


def membro_existe(telefone):
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("SELECT id_membro FROM membros WHERE telefone = %s LIMIT 1", (telefone,))
            return cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"Erro ao verificar existência do membro: {e}")
        return False


def salvar_novo_visitante(telefone, nome, origem="integra+"):
    """Salva um novo visitante no banco de dados com origem."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO visitantes (nome, telefone, data_cadastro, origem) 
                VALUES (%s, %s, NOW(), %s)
            ''', (nome, telefone, origem))
            conn.commit()
            logging.info(f"✅ Novo visitante {nome} registrado com sucesso.")
            return True
    except Exception as e:
        logging.error(f"Erro ao registrar novo visitante: {e}")
        return False


def buscar_numeros_telefone():
    """Busca os números de telefone dos visitantes no banco de dados."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute("SELECT telefone FROM visitantes")
            rows = cursor.fetchall() or []
            return [row.get("telefone") for row in rows if row.get("telefone")]
    except Exception as e:
        logging.error(f"Erro ao buscar números de telefone: {e}")
        return []


def visitante_existe(telefone):
    """Verifica se um visitante com o telefone especificado já existe."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM visitantes WHERE telefone = %s", (telefone,))
            result = cursor.fetchone() or {}
            return int(result.get("total", 0)) > 0
    except Exception as e:
        logging.error(f"Erro ao verificar visitante: {e}")
        return False


# =======================
# Status / Fases
# =======================
def atualizar_status(telefone: str, nova_fase_nome: str, origem="integra+"):
    """
    Atualiza ou insere o status (fase atual) do visitante no MySQL com base na tabela `fases`.
    """
    try:
        telefone = telefone.replace("+", "").replace(" ", "").strip()

        with closing(get_db_connection()) as conn:
            if not conn:
                logging.error("❌ Conexão com o banco falhou ao tentar atualizar status.")
                return False

            cursor = conn.cursor()

            # 1) Buscar visitante
            cursor.execute("SELECT id, nome FROM visitantes WHERE telefone = %s LIMIT 1", (telefone,))
            visitante = cursor.fetchone()
            if not visitante:
                logging.error(f"❌ Visitante com telefone '{telefone}' não encontrado no banco.")
                return False

            visitante_id = visitante["id"]
            nome_visitante = visitante.get("nome") or "Visitante"

            # 2) Buscar fase (tabela fases)
            cursor.execute("SELECT id FROM fases WHERE descricao = %s LIMIT 1", (nova_fase_nome,))
            fase_row = cursor.fetchone()
            if not fase_row:
                logging.error(f"❌ Fase '{nova_fase_nome}' não encontrada na tabela 'fases'.")
                return False

            fase_id = fase_row["id"]
            data_atualizacao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 3) Verificar se já existe status
            cursor.execute("SELECT id, fase_id FROM status WHERE visitante_id = %s LIMIT 1", (visitante_id,))
            status_existente = cursor.fetchone()

            if status_existente:
                fase_anterior = status_existente.get("fase_id")
                cursor.execute("""
                    UPDATE status 
                    SET fase_id = %s, data_atualizacao = %s, origem = %s 
                    WHERE visitante_id = %s
                """, (fase_id, data_atualizacao, origem, visitante_id))
                logging.info(
                    f"🔄 {nome_visitante} ({telefone}) mudou de fase_id={fase_anterior} → {fase_id} ({nova_fase_nome})"
                )
            else:
                cursor.execute("""
                    INSERT INTO status (visitante_id, fase_id, data_atualizacao, origem) 
                    VALUES (%s, %s, %s, %s)
                """, (visitante_id, fase_id, data_atualizacao, origem))
                logging.info(f"🆕 Status criado para {nome_visitante} ({telefone}) → fase '{nova_fase_nome}'")

            conn.commit()
            return True

    except Exception as e:
        logging.exception(f"❌ Erro inesperado ao atualizar status para o telefone {telefone}: {e}")
        return False


def buscar_fase_id(descricao_fase):
    """Busca o ID de uma fase com base na sua descrição."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM fases WHERE descricao = %s LIMIT 1", (descricao_fase,))
            fase = cursor.fetchone()
            return fase["id"] if fase else None
    except Exception as e:
        logging.error(f"Erro ao buscar fase: {e}")
        return None


def obter_estado_atual_do_banco(telefone):
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return "INICIO"
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COALESCE(f.descricao, 'INICIO') AS fase_atual
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                WHERE v.telefone = %s
                LIMIT 1
            ''', (telefone,))
            resultado = cursor.fetchone() or {}
            return resultado.get("fase_atual") or "INICIO"
    except Exception as e:
        logging.error(f"Erro ao obter estado do visitante {telefone}: {e}")
        return "INICIO"


# =======================
# Estatísticas
# =======================
def salvar_estatistica(numero, estado_atual, proximo_estado, origem="integra+"):
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO estatisticas (numero, estado_atual, proximo_estado, origem, data_hora)
                VALUES (%s, %s, %s, %s, %s)
            ''', (numero, estado_atual, proximo_estado, origem, datetime.now()))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Erro ao salvar estatística para {numero}: {e}")
        return False


def registrar_estatistica(numero, estado_atual, proximo_estado):
    try:
        salvar_estatistica(numero, estado_atual, proximo_estado)
        logging.info(f"📊 Estatística registrada para {numero}: {estado_atual} → {proximo_estado}")
    except Exception as e:
        logging.error(f"Erro ao registrar estatística para {numero}: {e}")


# =======================
# Conversas
# =======================
def salvar_conversa(numero: str, mensagem: str, tipo="recebida", sid=None, origem="integra+", visitante_id: int = None):
    """
    Salva conversa:
    - Se visitante_id vier, usa ele (mais confiável).
    - Caso contrário, resolve visitante pelo telefone (compatível com chamadas antigas).
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()

            if visitante_id:
                cursor.execute("""
                    INSERT INTO conversas (visitante_id, mensagem, tipo, message_sid, origem, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (visitante_id, mensagem, tipo, sid, origem))
            else:
                cursor.execute("""
                    INSERT INTO conversas (visitante_id, mensagem, tipo, message_sid, origem, created_at)
                    VALUES (
                        (SELECT id FROM visitantes WHERE telefone = %s LIMIT 1),
                        %s, %s, %s, %s, NOW()
                    )
                """, (numero, mensagem, tipo, sid, origem))

            conn.commit()
            logging.info(f"💬 Conversa salva: tel={numero}, tipo={tipo}, origem={origem}")
            return True

    except Exception as e:
        logging.error(f"Erro ao salvar conversa para o telefone {numero}. Detalhes: {e}")
        return False


def verificar_sid_existente(sid: str) -> bool:
    """✅ Corrigido: placeholder MySQL (%s) + DictCursor."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM conversas WHERE message_sid = %s LIMIT 1", (sid,))
            return cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"Erro ao verificar SID existente: {e}")
        return False


def mensagem_sid_existe(message_sid: str) -> bool:
    """✅ Corrigido: COUNT(*) com alias (DictCursor)."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM conversas WHERE message_sid = %s", (message_sid,))
            row = cursor.fetchone() or {}
            return int(row.get("total", 0)) > 0
    except Exception as e:
        logging.error(f"Erro ao verificar SID da mensagem: {e}")
        return False


def obter_conversa_por_visitante(visitante_id: int) -> str:
    """
    Retorna o histórico de conversas de um visitante em HTML formatado.
    ✅ Compatível com colunas data_hora e/ou created_at (usa COALESCE).
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return "<p>Erro ao obter conversa (sem conexão).</p>"
            cursor = conn.cursor()

            consulta_sql = """
            SELECT 
                CASE 
                    WHEN c.tipo = 'enviada' THEN 'Bot'
                    ELSE v.nome
                END AS remetente,
                c.mensagem,
                COALESCE(c.created_at, c.data_hora) AS data_hora,
                c.tipo
            FROM conversas c
            INNER JOIN visitantes v ON v.id = c.visitante_id
            WHERE c.visitante_id = %s
            ORDER BY COALESCE(c.created_at, c.data_hora);
            """

            cursor.execute(consulta_sql, (visitante_id,))
            conversas = cursor.fetchall() or []

            resultado = "<div class='chat-conversa'>"
            for conversa in conversas:
                classe = "bot" if conversa.get("tipo") == "enviada" else "user"
                resultado += (
                    f"<p class='{classe}'>"
                    f"<strong>{conversa.get('remetente','')}:</strong> {conversa.get('mensagem','')} "
                    f"<br><small>{conversa.get('data_hora','')}</small></p>"
                )
            resultado += "</div>"

            return resultado

    except Exception as e:
        logging.error(f"Erro ao buscar conversa para o visitante {visitante_id}: {e}")
        return "<p>Erro ao obter conversa.</p>"


# =======================
# Monitor / Listagens
# =======================
def monitorar_status_visitantes():
    """Retorna o status mais recente de todos os visitantes cadastrados, excluindo fase ID 11 (Importados)."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    v.id,
                    v.nome,
                    v.telefone,
                    COALESCE(f.descricao, 'Cadastrado') AS fase_atual
                FROM visitantes v
                LEFT JOIN status s 
                    ON s.id = (
                        SELECT MAX(s2.id)
                        FROM status s2
                        WHERE s2.visitante_id = v.id
                    )
                LEFT JOIN fases f 
                    ON s.fase_id = f.id
                WHERE f.id != 11 OR f.id IS NULL
                ORDER BY v.id DESC;
            ''')
            rows = cursor.fetchall() or []

            return [
                {
                    "id": row.get("id"),
                    "name": row.get("nome"),
                    "phone": row.get("telefone"),
                    "status": row.get("fase_atual") or "Cadastrado",
                }
                for row in rows
            ]

    except Exception as e:
        logging.error(f"Erro ao buscar status de visitantes no banco de dados: {e}")
        return []


def visitantes_listar_fases():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute(''' 
                SELECT v.nome, v.telefone, COALESCE(f.descricao, 'INICIO') AS fase_atual
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
            ''')
            return cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Erro ao buscar fases dos visitantes: {e}")
        return []


def visitantes_listar_estatisticas():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM estatisticas ORDER BY data_hora DESC")
            return cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas: {e}")
        return []


def visitantes_monitorar_status():
    """(compat)"""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.nome, v.telefone, COALESCE(f.descricao, 'INICIO') AS fase_atual
                FROM visitantes v 
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
            ''')
            return cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Erro ao buscar status de visitantes no banco de dados: {e}")
        return []


def listar_todos_visitantes():
    """
    ✅ PyMySQL DictCursor já retorna dict.
    Também retorna 'id' e 'visitante_id' para compatibilidade.
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()

            cursor.execute('''
                SELECT 
                    v.id AS id,
                    v.id AS visitante_id,
                    v.nome,
                    v.telefone,
                    v.email,
                    v.data_nascimento,
                    v.cidade,
                    v.genero,
                    v.estado_civil,
                    v.igreja_atual,
                    v.frequenta_igreja,
                    v.indicacao,
                    v.membro,
                    v.pedido_oracao,
                    v.horario_contato,
                    COALESCE(f.descricao, 'Cadastrado') AS fase,
                    i.tipo AS interacao_tipo,
                    i.data_hora AS interacao_data,
                    i.observacao AS interacao_observacao
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                LEFT JOIN fases f ON s.fase_id = f.id
                LEFT JOIN interacoes i ON v.id = i.visitante_id
                ORDER BY v.id DESC
            ''')

            return cursor.fetchall() or []

    except Exception as e:
        logging.error(f"Erro ao buscar visitantes no banco de dados: {e}")
        return []


def listar_visitantes_fase_null():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute('''
                SELECT v.id, v.nome, v.telefone 
                FROM visitantes v
                LEFT JOIN status s ON v.id = s.visitante_id
                WHERE s.fase_id IS NULL
                ORDER BY v.id DESC
            ''')
            rows = cursor.fetchall() or []
            return [{"id": r.get("id"), "name": r.get("nome"), "phone": r.get("telefone")} for r in rows]
    except Exception as e:
        logging.error(f"Erro ao listar visitantes com fase NULL: {e}")
        return []


# =======================
# Dados do visitante
# =======================
def obter_dados_visitante(telefone: str) -> Optional[Dict]:
    query = """
        SELECT nome, email, data_nascimento, cidade, genero, estado_civil 
        FROM visitantes 
        WHERE telefone = %s
        LIMIT 1
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute(query, (telefone,))
            return cursor.fetchone()
    except Exception as e:
        logging.error(f"Erro ao buscar dados do visitante: {e}")
        return None


def obter_nome_do_visitante(telefone: str) -> str:
    try:
        telefone_normalizado = normalizar_para_recebimento(telefone)

        with closing(get_db_connection()) as conn:
            if not conn:
                return "Visitante não Cadastrado"
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM visitantes WHERE telefone = %s LIMIT 1", (telefone_normalizado,))
            resultado = cursor.fetchone() or {}
            return resultado.get("nome") or "Visitante não Cadastrado"

    except Exception as e:
        logging.error(f"Erro ao buscar nome do visitante: {e}")
        return "Sem dados!"


def atualizar_dado_visitante(numero, campo, valor):
    """Atenção: campo vem de código (não do usuário)."""
    query = f"UPDATE visitantes SET {campo} = %s WHERE telefone = %s"
    with closing(get_db_connection()) as conn:
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute(query, (valor, numero))
        conn.commit()
        return True


def salvar_pedido_oracao(telefone, pedido, origem="integra+"):
    """Salva o pedido de oração com origem."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cursor = conn.cursor()
            cursor.execute(''' 
                UPDATE visitantes SET pedido_oracao = %s, origem = %s
                WHERE telefone = %s
            ''', (pedido, origem, telefone))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Erro ao salvar pedido de oração: {e}")
        return False


# =======================
# Normalização (WhatsApp)
# =======================
def normalizar_para_envio(telefone: str) -> str:
    """
    Normaliza um número para envio via WhatsApp/Z-API.
    Retorna no formato internacional: 55 + DDD + número.
    Ex: 48999999999 -> 5548999999999
    """
    telefone = ''.join(filter(str.isdigit, telefone))

    if telefone.startswith('55') and len(telefone) == 13:
        return telefone

    if len(telefone) == 11:
        return f"55{telefone}"

    raise ValueError(f"Telefone inválido para envio: {telefone}")


def normalizar_para_recebimento(telefone: str) -> str:
    """
    Normaliza o telefone recebido para salvar no banco:
    - remove whatsapp:
    - remove 55
    - garante 11 dígitos (DDD + 9 + número) quando vier com 10
    """
    logging.info(f"Recebendo telefone para normalização: {telefone}")

    if telefone.startswith('whatsapp:'):
        telefone = telefone.replace('whatsapp:', '')
        logging.info(f"Prefixo 'whatsapp:' removido, número agora é: {telefone}")

    telefone = ''.join(filter(str.isdigit, telefone))

    if telefone.startswith('55'):
        telefone = telefone[2:]

    if len(telefone) == 10:
        telefone = f"{telefone[:2]}9{telefone[2:]}"
    elif len(telefone) == 11:
        pass
    else:
        logging.error(f"Número de telefone inválido após normalização: {telefone}")
        raise ValueError(f"Número de telefone inválido: {telefone}")

    logging.info(f"Número normalizado para: {telefone}")
    return telefone


# =======================
# Contagens / Indicadores
# =======================
def visitantes_contar_novos():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM visitantes WHERE data_nascimento IS NOT NULL")
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar novos visitantes: {e}")
        return 0


def visitantes_contar_membros_interessados():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM status 
                WHERE fase_id = (SELECT id FROM fases WHERE descricao = 'INTERESSE_DISCIPULADO' LIMIT 1)
            """)
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar membros interessados: {e}")
        return 0


def visitantes_contar_sem_retorno():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM visitantes WHERE horario_contato IS NULL")
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar visitantes sem retorno: {e}")
        return 0


def visitantes_contar_discipulado_enviado():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM status
                WHERE fase_id = (SELECT id FROM fases WHERE descricao = 'INTERESSE_DISCIPULADO' LIMIT 1)
            """)
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar visitantes enviados ao discipulado: {e}")
        return 0


def visitantes_contar_sem_interesse_discipulado():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM status
                WHERE fase_id = (SELECT id FROM fases WHERE descricao = 'INTERESSE_NOVO_COMEC' LIMIT 1)
            """)
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar visitantes sem interesse no discipulado: {e}")
        return 0


def visitantes_contar_sem_retorno_total():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM status WHERE fase_id IS NULL")
            row = cursor.fetchone() or {}
            return int(row.get("total", 0))
    except Exception as e:
        logging.error(f"Erro ao contar visitantes sem retorno total: {e}")
        return 0


def obter_total_visitantes():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return "0"
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM visitantes")
            row = cursor.fetchone() or {}
            total = int(row.get("total", 0))
            return formatar_com_pontos(total)
    except Exception as e:
        logging.error(f"Erro ao obter total de visitantes: {e}")
        return "0"


def obter_total_membros():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0, 0, 0
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_membros,
                    SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) AS total_homensmembro,
                    SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) AS total_mulheresmembro
                FROM membros
            """)
            result = cursor.fetchone() or {}
            total_membros = int(result.get("total_membros") or 0)
            total_homensmembro = int(result.get("total_homensmembro") or 0)
            total_mulheresmembro = int(result.get("total_mulheresmembro") or 0)
            return total_membros, total_homensmembro, total_mulheresmembro
    except Exception as e:
        logging.error(f"Erro ao obter total de membros: {e}")
        return 0, 0, 0


def obter_total_discipulados():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return 0, 0, 0
            cursor = conn.cursor()
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
            result = cursor.fetchone() or {}
            return (
                int(result.get("total_discipulado") or 0),
                int(result.get("total_homens") or 0),
                int(result.get("total_mulheres") or 0),
            )
    except Exception as e:
        logging.error(f"Erro ao obter total de discipulados: {e}")
        return 0, 0, 0


def obter_dados_genero():
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return {"Homens": 0, "Homens_Percentual": 0, "Mulheres": 0, "Mulheres_Percentual": 0}
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) AS Homens,
                    ROUND(SUM(CASE WHEN genero = 'masculino' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS Homens_Percentual,
                    SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) AS Mulheres,
                    ROUND(SUM(CASE WHEN genero = 'feminino' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS Mulheres_Percentual
                FROM visitantes;
            """)
            result = cursor.fetchone() or {}
            return {
                "Homens": int(result.get("Homens") or 0),
                "Homens_Percentual": int(result.get("Homens_Percentual") or 0),
                "Mulheres": int(result.get("Mulheres") or 0),
                "Mulheres_Percentual": int(result.get("Mulheres_Percentual") or 0),
            }
    except Exception as e:
        logging.error(f"Erro ao obter dados de gênero: {e}")
        return {"Homens": 0, "Homens_Percentual": 0, "Mulheres": 0, "Mulheres_Percentual": 0}


def formatar_com_pontos(numero):
    return "{:,.0f}".format(numero).replace(",", ".")


# =======================
# Treinamento IA
# =======================
def salvar_par_treinamento(pergunta: str, resposta: str, categoria: str = "geral", fonte: str = "manual"):
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
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question, answer FROM training_pairs 
            ORDER BY id DESC LIMIT 1000
        """)
        pares = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return pares
    except Exception as e:
        logging.error(f"Erro ao obter pares de treinamento: {e}")
        return []


def obter_perguntas_pendentes():
    try:
        conn = get_db_connection()
        if not conn:
            return []
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, question, created_at 
            FROM unknown_questions 
            WHERE status = 'pending' 
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        perguntas = cursor.fetchall() or []
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


# =======================
# Campanhas / Eventos
# =======================
def salvar_envio_evento(visitante_id, evento_nome, mensagem, imagem_url=None, status="pendente", origem="integra+"):
    """Salva envio e atualiza fase do visitante para EVENTO_ENVIADO."""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # garantir fase EVENTO_ENVIADO
        cursor.execute("SELECT id FROM fases WHERE descricao = %s LIMIT 1", ("EVENTO_ENVIADO",))
        fase_row = cursor.fetchone()
        if not fase_row:
            cursor.execute("INSERT INTO fases (descricao) VALUES (%s)", ("EVENTO_ENVIADO",))
            conn.commit()
            cursor.execute("SELECT id FROM fases WHERE descricao = %s LIMIT 1", ("EVENTO_ENVIADO",))
            fase_row = cursor.fetchone()

        fase_id = fase_row["id"]

        # atualizar/ inserir status
        cursor.execute("""
            INSERT INTO status (visitante_id, fase_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE fase_id = VALUES(fase_id)
        """, (visitante_id, fase_id))

        # registrar envio
        cursor.execute("""
            INSERT INTO eventos_envios
                (visitante_id, evento_nome, mensagem, imagem_url, status, origem, data_envio)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """, (visitante_id, evento_nome, mensagem, imagem_url, status, origem))

        conn.commit()
        cursor.close()
        conn.close()

        logging.info(f"📢 Evento '{evento_nome}' salvo e fase do visitante {visitante_id} atualizada para EVENTO_ENVIADO")
        return True

    except Exception as e:
        logging.error(f"Erro ao salvar envio de evento: {e}")
        return False


def atualizar_status_envio_evento(visitante_id, evento_nome, novo_status):
    """Atualiza o status de um envio específico."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE eventos_envios
            SET status = %s, data_envio = NOW()
            WHERE visitante_id = %s AND evento_nome = %s
        """, (novo_status, visitante_id, evento_nome))
        conn.commit()
        cursor.close()
        conn.close()
        logging.debug(f"🟢 Status atualizado para {novo_status} ({visitante_id} - {evento_nome})")
        return True
    except Exception as e:
        logging.error(f"Erro ao atualizar status do envio: {e}")
        return False


def listar_envios_eventos(limit=100, origem: str = None):
    """Lista os últimos envios de eventos/campanhas, opcionalmente filtrando por origem."""
    try:
        conn = get_db_connection()
        if not conn:
            return []

        cursor = conn.cursor()
        base_query = """
            SELECT e.id, v.nome, v.telefone, e.evento_nome, e.mensagem, 
                   e.imagem_url, e.status, e.origem, e.data_envio
            FROM eventos_envios e
            JOIN visitantes v ON v.id = e.visitante_id
        """
        params = []

        if origem:
            base_query += " WHERE e.origem = %s"
            params.append(origem)

        base_query += " ORDER BY e.data_envio DESC LIMIT %s"
        params.append(int(limit))

        cursor.execute(base_query, tuple(params))
        rows = cursor.fetchall() or []
        cursor.close()
        conn.close()
        return rows

    except Exception as e:
        logging.error(f"Erro ao listar envios de eventos: {e}")
        return []


def filtrar_visitantes_para_evento(data_inicio=None, data_fim=None, idade_min=None, idade_max=None, genero=None):
    """
    Retorna visitantes filtrados por data de cadastro, idade e gênero.
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            query = """
                SELECT id, nome, telefone, genero, data_nascimento, data_cadastro
                FROM visitantes
                WHERE 1=1
            """
            params = []

            if data_inicio:
                query += " AND data_cadastro >= %s"
                params.append(data_inicio)

            if data_fim:
                query += " AND data_cadastro <= %s"
                params.append(data_fim)

            if genero:
                query += " AND genero = %s"
                params.append(genero)

            if idade_min is not None or idade_max is not None:
                query += " AND data_nascimento IS NOT NULL"
                if idade_min is not None:
                    query += " AND TIMESTAMPDIFF(YEAR, data_nascimento, CURDATE()) >= %s"
                    params.append(int(idade_min))
                if idade_max is not None:
                    query += " AND TIMESTAMPDIFF(YEAR, data_nascimento, CURDATE()) <= %s"
                    params.append(int(idade_max))

            cursor.execute(query, tuple(params))
            return cursor.fetchall() or []

    except Exception as e:
        logging.error(f"❌ Erro ao filtrar visitantes para evento: {e}")
        return []


def limpar_envios_eventos():
    """Remove todos os registros de campanhas enviadas."""
    try:
        conn = get_db_connection()
        if not conn:
            return 0
        cursor = conn.cursor()
        cursor.execute("DELETE FROM eventos_envios")
        total = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return total
    except Exception as e:
        logging.error(f"Erro ao limpar envios: {e}")
        return 0


def obter_resumo_campanhas(limit=100):
    """Resumo agrupado das campanhas por evento."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            cursor = conn.cursor()
            query = """
                SELECT 
                    evento_nome,
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'pendente' THEN 1 ELSE 0 END) AS pendentes,
                    SUM(CASE WHEN status = 'falha' THEN 1 ELSE 0 END) AS falhas,
                    SUM(CASE WHEN status IN ('enviado', 'reprocessado') THEN 1 ELSE 0 END) AS enviados,
                    MAX(data_envio) AS ultima_data
                FROM eventos_envios
                GROUP BY evento_nome
                ORDER BY ultima_data DESC
                LIMIT %s
            """
            cursor.execute(query, (int(limit),))
            return cursor.fetchall() or []
    except Exception as e:
        logging.error(f"Erro ao obter resumo de campanhas: {e}")
        return []
