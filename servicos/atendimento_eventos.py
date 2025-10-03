import logging
from database import salvar_conversa, atualizar_status
from servicos.fila_mensagens import adicionar_na_fila
from constantes import EstadoVisitante

def processar_evento_enviado(numero: str, nome_visitante: str, message_sid: str, origem: str = "integra+"):
    """
    Processa quando o visitante recebeu convite de evento e precisa escolher uma opção.
    """
    resposta = (f"👋 Oi {nome_visitante}, vi que você recebeu nosso convite para o evento! 🎉\n"
                "Gostaria de confirmar sua presença ou saber mais detalhes?\n\n"
                "Responda com:\n"
                "1️⃣ Sim, quero participar!\n"
                "2️⃣ Quero saber mais informações.\n"
                "3️⃣ Não posso participar desta vez.")

    try:
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)
        adicionar_na_fila(numero, resposta)
        salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

        return {
            "resposta": resposta,
            "estado_atual": "EVENTO_ENVIADO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    except Exception as e:
        logging.error(f"Erro ao processar evento enviado para {numero}: {e}")
        return {
            "resposta": None,
            "estado_atual": "ERRO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }
