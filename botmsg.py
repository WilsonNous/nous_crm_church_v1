import os
import logging
from flask import Flask, request, jsonify
from servicos.processamento_mensagens import processar_mensagem

# =======================
# Configuração do Flask
# =======================
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# =======================
# Configurações Z-API
# =======================
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# =======================
# Webhook para receber mensagens
# =======================
@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Recebe mensagens do WhatsApp via Z-API ou Twilio e envia para o processador central.
    """
    try:
        dados = request.json
        numero = dados.get("from") or dados.get("numero")
        texto = dados.get("message") or dados.get("texto")
        message_sid = dados.get("sid") or dados.get("message_sid") or "SEM_SID"

        # Ignorar mensagens vazias (caso do Twilio ou Z-API quando não vem corpo)
        if not texto or not numero:
            logging.warning("🚫 Mensagem ignorada (sem texto ou sem número).")
            return jsonify({"status": "ignored"}), 200

        logging.info(f"📩 Mensagem recebida | Número={numero} | Texto={texto}")

        # Chama o processador principal
        resposta = processar_mensagem(numero, texto, message_sid, origem="integra+")

        return jsonify({"status": "ok", "resposta": resposta}), 200

    except Exception as e:
        logging.error(f"❌ Erro no webhook: {e}")
        return jsonify({"status": "erro", "detalhe": str(e)}), 500


# =======================
# Inicialização do servidor
# =======================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
