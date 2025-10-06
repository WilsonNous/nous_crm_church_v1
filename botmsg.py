# botmsg.py - Orquestrador do Bot Integra+
import logging
from servicos.processamento_mensagens import processar_mensagem
from database import normalizar_para_recebimento, verificar_sid_existente

def tratar_mensagem_webhook(dados: dict, origem="integra+"):
    """
    Função de entrada chamada pelas rotas (/api/webhook-zapi, etc).
    Valida dados recebidos, normaliza número, evita duplicidades
    e aciona o processador central.
    """
    try:
        # Extrai informações principais
        numero = dados.get("phone") or dados.get("from") or dados.get("numero")
        texto = (
            (dados.get("text") or {}).get("message")
            if isinstance(dados.get("text"), dict)
            else dados.get("message") or dados.get("body") or dados.get("texto")
        )
        message_sid = dados.get("sid") or dados.get("messageId") or dados.get("message_sid") or "SEM_SID"

        # Ignorar mensagens sem corpo ou número
        if not texto or not numero:
            logging.warning("🚫 Mensagem ignorada (sem texto ou sem número).")
            return {"status": "ignored", "resposta": None}

        # Ignorar mensagens enviadas pelo próprio bot
        if dados.get("fromMe") or dados.get("fromApi"):
            logging.info("🛑 Ignorado: mensagem enviada pelo próprio bot (fromMe=True).")
            return {"status": "ignored", "resposta": None}

        # Normaliza o número
        numero_normalizado = normalizar_para_recebimento(numero)

        # Evita reprocessar o mesmo SID
        if verificar_sid_existente(message_sid):
            logging.debug(f"🟡 Ignorado: mensagem {message_sid} já registrada.")
            return {"status": "duplicada", "resposta": None}

        logging.info(f"📥 Mensagem recebida | Origem={origem} | Número={numero_normalizado} | Texto={texto}")

        # Chama o processador principal
        resposta = processar_mensagem(numero_normalizado, texto, message_sid, origem=origem)

        return {"status": "ok", "resposta": resposta}

    except Exception as e:
        logging.error(f"❌ Erro no tratamento da mensagem: {e}", exc_info=True)
        return {"status": "erro", "detalhe": str(e)}
