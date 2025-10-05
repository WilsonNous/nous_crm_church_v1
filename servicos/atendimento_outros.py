import logging
from datetime import datetime
from database import salvar_conversa, atualizar_status, normalizar_para_envio
from servicos.fila_mensagens import adicionar_na_fila
from constantes import EstadoVisitante
from servicos.interacoes_basicas import detectar_agradecimento, detectar_palavra_chave_ministerio

# Número da secretaria para assuntos gerais
NUMERO_SECRETARIA = "48991553619"

def processar_outro(numero: str, visitor_name: str, texto_recebido: str, message_sid: str, origem: str = "integra+"):
    """
    Processa mensagens classificadas como 'OUTRO':
    - Se encontrar palavra-chave de ministério → responde direto.
    - Se for agradecimento → responde com cordialidade.
    - Caso contrário → envia para a secretaria.
    """

    texto = texto_recebido.lower().strip()

    # 🔎 Verificar palavra-chave de ministério
    resposta_ministerio = detectar_palavra_chave_ministerio(texto)
    if resposta_ministerio:
        adicionar_na_fila(numero, resposta_ministerio)
        salvar_conversa(numero, resposta_ministerio, tipo="enviada", sid=message_sid, origem=origem)
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)
        return {
            "resposta": resposta_ministerio,
            "estado_atual": "MINISTERIO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    # 🙏 Verificar se é um agradecimento
    if detectar_agradecimento(texto):
        resposta_agradecimento = (f"Ficamos felizes em poder ajudar, {visitor_name}! "
                                  "Se precisar de algo mais, estamos à disposição. 🙌")
        adicionar_na_fila(numero, resposta_agradecimento)
        salvar_conversa(numero, resposta_agradecimento, tipo="enviada", sid=message_sid, origem=origem)
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)
        return {
            "resposta": resposta_agradecimento,
            "estado_atual": "AGRADECIMENTO",
            "proximo_estado": EstadoVisitante.INICIO.name
        }

    # 📩 Caso não seja ministério nem agradecimento → encaminhar para secretaria
    salvar_conversa(numero, f"Outro: {texto_recebido}", tipo="recebida", sid=message_sid, origem=origem)

    mensagem_secretaria = (
        f"📌 Solicitação de Atendimento (Outro)\n\n"
        f"👤 Visitante: {visitor_name}\n"
        f"📱 Número: {numero}\n"
        f"💬 Mensagem: {texto_recebido}\n"
        f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    try:
        numero_secretaria = normalizar_para_envio(NUMERO_SECRETARIA)
        adicionar_na_fila(numero_secretaria, mensagem_secretaria)
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem 'Outro' para secretaria: {e}")

    resposta = (f"Entendido, {visitor_name}. Sua solicitação foi encaminhada "
                f"para a nossa secretaria, e em breve entraremos em contato com você. 🙂")

    atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)
    adicionar_na_fila(numero, resposta)
    salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

    return {
        "resposta": resposta,
        "estado_atual": EstadoVisitante.OUTRO.name,
        "proximo_estado": EstadoVisitante.INICIO.name
    }
