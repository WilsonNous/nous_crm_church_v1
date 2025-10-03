import logging
from constantes import EstadoVisitante, mensagens

# =======================
# Definição das transições
# =======================
TRANSICOES = {
    EstadoVisitante.INICIO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "batizado": EstadoVisitante.INTERESSE_DISCIPULADO,
        "novo começo": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "oração": EstadoVisitante.PEDIDO_ORACAO,
        "horários": EstadoVisitante.HORARIOS,
        "grupo": EstadoVisitante.LINK_WHATSAPP,
        "outro": EstadoVisitante.OUTRO,
    },
    EstadoVisitante.INTERESSE_DISCIPULADO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.INTERESSE_NOVO_COMEC: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.PEDIDO_ORACAO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.HORARIOS: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.OUTRO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.LINK_WHATSAPP: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO,
    },
    EstadoVisitante.FIM: {
        "default": EstadoVisitante.INICIO,
    },
}


# =======================
# Função para buscar próximo estado
# =======================
def obter_proximo_estado(estado_atual, mensagem_normalizada: str):
    """
    Dado o estado atual e a mensagem recebida, retorna o próximo estado.
    """
    transicoes = TRANSICOES.get(estado_atual, {})
    proximo = transicoes.get(mensagem_normalizada)

    if proximo is None and "default" in transicoes:
        proximo = transicoes["default"]

    logging.debug(f"Transição de {estado_atual.name} com msg '{mensagem_normalizada}' → {getattr(proximo, 'name', None)}")
    return proximo


# =======================
# Função para obter mensagem padrão
# =======================
def obter_mensagem_estado(proximo_estado, visitor_name: str):
    """
    Retorna a mensagem correspondente ao próximo estado,
    ou uma resposta padrão se não existir.
    """
    return mensagens.get(proximo_estado, f"Desculpe, {visitor_name}, não entendi sua resposta.")

