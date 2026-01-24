import logging
import pymysql
from database import get_db_connection, salvar_conversa, atualizar_status
from servicos.fila_mensagens import adicionar_na_fila
from servicos.interacoes_basicas import detectar_saudacao, detectar_agradecimento, detectar_palavra_chave_ministerio
from constantes import EstadoVisitante

# IA Integrada
from ia_integracao import IAIntegracao
ia_integracao = IAIntegracao()

def buscar_ultima_pergunta(numero: str, message_sid: str):
    """Busca a última pergunta recebida do visitante para dar contexto à IA"""
    ultima = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT mensagem FROM conversas 
            WHERE visitante_id = (SELECT id FROM visitantes WHERE telefone = %s) 
            AND tipo = 'recebida' 
            AND message_sid != %s
            ORDER BY data_hora DESC LIMIT 1
        """, (numero, message_sid))
        result = cursor.fetchone()
        if result:
            ultima = result["mensagem"]
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao buscar última pergunta do visitante {numero}: {e}")
    return ultima


def processar_com_ia(numero: str, texto_recebido: str, texto_recebido_normalizado: str,
                     estado_atual, message_sid: str, origem: str = "integra+"):
    """
    Usa a IA para responder mensagens fora do fluxo normal.
    Se a confiança for baixa, tenta cair em outros detectores (saudação, agradecimento, ministério).
    """
    ultima_pergunta = buscar_ultima_pergunta(numero, message_sid)

    # Pergunta para a IA
    resultado_ia = ia_integracao.responder_pergunta(pergunta_usuario=texto_recebido)

    if resultado_ia[0] and resultado_ia[1] > 0.2:  # resposta e confiança mínima
        logging.info(f"IA respondeu com confiança {resultado_ia[1]:.2f}: {resultado_ia[0]}")
        adicionar_na_fila(numero, resultado_ia[0])
        salvar_conversa(numero, resultado_ia[0], tipo="enviada", sid=message_sid, origem=origem)
        atualizar_status(numero, EstadoVisitante.INICIO.value)
        return {
            "resposta": resultado_ia[0],
            "estado_atual": estado_atual.name,
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    # Se IA não respondeu bem, tenta fallback: ministério, saudação, agradecimento
    resposta_ministerio = detectar_palavra_chave_ministerio(texto_recebido_normalizado)
    if resposta_ministerio:
        adicionar_na_fila(numero, resposta_ministerio)
        salvar_conversa(numero, resposta_ministerio, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta_ministerio,
            "estado_atual": "MINISTERIO",
            "proximo_estado": "INICIO"
        }

    if detectar_saudacao(texto_recebido_normalizado):
        resposta_saudacao = "Oi! Que bom te ver por aqui 😊. Como posso ajudar você hoje?"
        adicionar_na_fila(numero, resposta_saudacao)
        salvar_conversa(numero, resposta_saudacao, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta_saudacao,
            "estado_atual": "SAUDACAO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    if detectar_agradecimento(texto_recebido_normalizado):
        resposta_agradecimento = "Ficamos felizes em poder ajudar! Se precisar de algo mais, estamos à disposição. 🙌"
        adicionar_na_fila(numero, resposta_agradecimento)
        salvar_conversa(numero, resposta_agradecimento, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta_agradecimento,
            "estado_atual": "AGRADECIMENTO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    # Se nada foi detectado → resposta padrão de erro cordial
    resposta_fallback = (
    "Tudo bem 😊 talvez eu não tenha entendido sua resposta.\n\n"
    "Vamos tentar novamente?\n\n"
    "👉 *Aqui, consideramos batismo como o batismo nas águas por imersão, feito de forma consciente.*\n\n"
    "Escolha uma das opções abaixo:\n\n"
    "1⃣ Já fiz batismo nas águas (imersão) e quero me tornar membro.\n"
    "2⃣ Ainda não fiz batismo nas águas (imersão) *(ou fui batizado quando criança)* e quero me tornar membro.\n"
    "3⃣ 🙏 Gostaria de receber orações.\n"
    "4⃣ 🕒 Quero saber mais sobre os horários dos cultos.\n"
    "5⃣ 👥 Quero entrar no grupo do WhatsApp da igreja.\n"
    "6⃣ ✍️ Outro assunto.\n\n"
    "Estou aqui pra te ajudar 🙌"
    )

    adicionar_na_fila(numero, resposta_fallback)
    salvar_conversa(numero, resposta_fallback, tipo="enviada", sid=message_sid, origem=origem)

    return {
        "resposta": resposta_fallback,
        "estado_atual": estado_atual.name,
        "proximo_estado": estado_atual.name
    }
