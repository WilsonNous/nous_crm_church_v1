import logging
from utilitarios.texto import normalizar_texto
from database import obter_nome_do_visitante, salvar_conversa, atualizar_status
from constantes import EstadoVisitante
from servicos.fila_mensagens import enviar_mensagem_para_fila

def detectar_agradecimento(texto: str) -> bool:
    """
    Detecta expressões de agradecimento em uma mensagem.
    """
    palavras_agradecimento = [
        "obrigado", "obrigada", "grato", "grata",
        "agradecido", "agradecida", "muito obrigado", "muito obrigada",
        "amem", "amém", "aleluia", "gloria a deus"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(palavra in texto_normalizado for palavra in palavras_agradecimento)


def processar_agradecimento(numero: str, message_sid: str, origem: str = "integra+") -> dict:
    """
    Responde automaticamente a mensagens de agradecimento.
    """
    try:
        visitor_name = obter_nome_do_visitante(numero)
        if visitor_name:
            visitor_name = visitor_name.split()[0]
        else:
            visitor_name = "Visitante"

        resposta = (
            f"Ficamos felizes em poder ajudar, {visitor_name}! 🙌 "
            f"Se precisar de algo mais, estamos à disposição."
        )

        # Atualiza o status do visitante
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)

        # Envia e salva a resposta
        enviar_mensagem_para_fila(numero, resposta)
        salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

        logging.info(f"🙏 Agradecimento processado para {numero}")

        return {
            "resposta": resposta,
            "estado_atual": "AGRADACIMENTO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    except Exception as e:
        logging.error(f"Erro ao processar agradecimento para {numero}: {e}")
        return {"erro": str(e)}
