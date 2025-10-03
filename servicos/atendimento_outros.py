import logging
from datetime import datetime
from database import normalizar_para_envio, salvar_conversa, atualizar_status, registrar_estatistica
from servicos.fila_mensagens import adicionar_na_fila
from constantes import EstadoVisitante

def processar_outros(numero_visitante: str, nome_visitante: str, mensagem_recebida: str, numero_secretaria: str, message_sid: str, origem: str = "integra+"):
    """
    Processa mensagens do tipo 'Outro':
    - Salva no banco
    - Notifica a secretaria
    - Responde ao visitante
    """
    # Salva a mensagem como 'Outro'
    salvar_conversa(numero_visitante, f"Outro: {mensagem_recebida}", tipo='recebida', sid=message_sid, origem=origem)

    # Monta mensagem para secretaria
    mensagem_secretaria = (
        f"📌 Solicitação de Atendimento (Outro)\n\n"
        f"👤 Visitante: {nome_visitante}\n"
        f"📱 Número: {numero_visitante}\n"
        f"💬 Mensagem: {mensagem_recebida}\n"
        f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    try:
        numero_normalizado_secretaria = normalizar_para_envio(numero_secretaria)
        adicionar_na_fila(numero_normalizado_secretaria, mensagem_secretaria)
    except Exception as e:
        logging.error(f"Erro ao enviar a mensagem 'Outro' para a secretaria: {e}")

    # Resposta automática ao visitante
    resposta = (f"Entendido, {nome_visitante}. "
                f"Sua solicitação foi encaminhada para a nossa secretaria, "
                f"e em breve entraremos em contato com você. 🙂")

    proximo_estado = EstadoVisitante.FIM
    atualizar_status(numero_visitante, EstadoVisitante.FIM.value)
    atualizar_status(numero_visitante, EstadoVisitante.INICIO.value)  # Reset para novo atendimento

    adicionar_na_fila(numero_visitante, resposta)
    salvar_conversa(numero_visitante, resposta, tipo='enviada', sid=message_sid, origem=origem)
    registrar_estatistica(numero_visitante, EstadoVisitante.OUTRO.value, proximo_estado.value)

    return {
        "resposta": resposta,
        "estado_atual": EstadoVisitante.OUTRO.name,
        "proximo_estado": EstadoVisitante.FIM.name
    }

