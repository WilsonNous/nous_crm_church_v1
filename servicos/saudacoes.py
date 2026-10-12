import logging
from utilitarios.texto import normalizar_texto
from database import obter_nome_do_visitante, salvar_conversa, atualizar_status
from constantes import EstadoVisitante
from servicos.fila_mensagens import enviar_mensagem_para_fila

def detectar_saudacao(texto: str) -> bool:
    """
    Verifica se a mensagem contém uma saudação comum.
    """
    saudacoes = [
        "ola", "oi", "bom dia", "boa tarde", "boa noite",
        "eae", "e aí", "saudacoes", "a paz do senhor", "a paz de cristo", "paz"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(saudacao in texto_normalizado for saudacao in saudacoes)


def processar_saudacao(numero: str, message_sid: str, origem: str = "integra+", is_webhook_reply: bool = False) -> dict:
    """
    Processa mensagens de saudação e envia a resposta inicial do Integra+.
    """
    try:
        visitor_name = obter_nome_do_visitante(numero)
        if visitor_name:
            visitor_name = visitor_name.split()[0]
        else:
            visitor_name = "Visitante"

        resposta = f"""Olá, {visitor_name}!   
Sou o _*Integra+*_, assistente do Ministério de Integração da MAIS DE CRISTO Canasvieiras.

Como posso te ajudar hoje?

1️⃣ *Já fiz batismo nas águas (imersão)* e quero me tornar membro  
2️⃣ *Ainda não fiz batismo nas águas (imersão)* *(ou fui batizado quando criança)* e quero me tornar membro  
3️⃣ Gostaria de receber orações  
4️⃣ Quero saber os horários dos cultos  
5️⃣ Entrar no grupo do WhatsApp  
6️⃣ Outro assunto  

Estou aqui pra caminhar com você! """


        # Atualiza o status e envia resposta
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)
        enviar_mensagem_para_fila(numero, resposta, meta={"tipo": "bot", "is_reply": bool(is_webhook_reply), "origem": origem, "sid_origem": message_sid})
        salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

        logging.info(f"🤝 Saudação processada para {numero}")

        return {
            "resposta": resposta,
            "estado_atual": "SAUDACAO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    except Exception as e:
        logging.error(f"Erro ao processar saudação para {numero}: {e}")
        return {"erro": str(e)}
