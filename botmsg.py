# botmsg.py - Orquestrador do Bot Integra+
import logging
from servicos.processamento_mensagens import processar_mensagem

def tratar_mensagem_webhook(dados: dict, origem="integra+"):
    """
    Função de entrada chamada pelas rotas (/api/webhook-zapi, etc).
    Valida dados recebidos e aciona o processador central.
    """
    try:
        numero = dados.get("from") or dados.get("numero")
        texto = dados.get("message") or dados.get("texto")
        message_sid = dados.get("sid") or dados.get("message_sid") or "SEM_SID"

        # Ignorar mensagens sem corpo ou sem número
        if not texto or not numero:
            logging.warning("🚫 Mensagem ignorada (sem texto ou sem número).")
            return {"status": "ignored", "resposta": None}

        logging.info(f"📥 Mensagem recebida | Origem={origem} | Número={numero} | Texto={texto}")
        resposta = processar_mensagem(numero, texto, message_sid, origem=origem)

        return {"status": "ok", "resposta": resposta}

    except Exception as e:
        logging.error(f"❌ Erro no tratamento da mensagem: {e}")
        return {"status": "erro", "detalhe": str(e)}
