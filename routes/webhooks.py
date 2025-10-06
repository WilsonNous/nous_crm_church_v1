import logging
from flask import request, jsonify
from botmsg import processar_mensagem
from database import normalizar_para_recebimento
from constantes import DEBUG

def register(app):

    # --- Webhook TWILIO ---
    @app.route('/api/webhook', methods=['POST'])
    def webhook_twilio():
        try:
            data = request.get_json(silent=True) or request.form
            from_number = data.get('From', '') or data.get('numero', '')
            message_body = data.get('Body', '').strip() if 'Body' in data else data.get('mensagem', '').strip()
            message_sid = data.get('MessageSid', '') or data.get('sid', '')
            origem = data.get('origem') or request.args.get('origem', 'integra+')

            logging.info(f"📥 Webhook TWILIO | Origem={origem} | From={from_number} | SID={message_sid} | Msg={message_body}")

            processar_mensagem(from_number, message_body, message_sid, origem=origem)
            return jsonify({"status": "success", "origem": origem}), 200

        except Exception as e:
            logging.error(f"❌ Erro no webhook TWILIO: {e}", exc_info=True)
            return jsonify({"error": "Erro ao processar webhook Twilio"}), 500


    # --- Webhook Z-API ---
    @app.route('/api/webhook-zapi', methods=['POST'])
    def webhook_zapi():
        try:
            data = request.get_json(silent=True)
            if not data:
                raw_body = request.data.decode('utf-8', errors='ignore')
                logging.warning(f"⚠️ Webhook Z-API recebido como texto: {raw_body[:300]}")
                return jsonify({"status": "ignored", "reason": "invalid_json"}), 200

            # Log resumido
            if DEBUG:
                logging.info(f"📦 Payload Z-API completo: {data}")
            else:
                msg = ""
                if isinstance(data.get("text"), dict):
                    msg = data["text"].get("message", "")
                elif "message" in data:
                    msg = data["message"]
                logging.debug(f"📦 Z-API resumido: phone={data.get('phone')}, fromMe={data.get('fromMe')}, msg={msg[:80]}...")

            from_number = data.get("phone") or data.get("sender") or data.get("from") or "?"
            message_sid = data.get("messageId") or data.get("id") or "?"
            message_body = ""

            # Extrai texto da mensagem
            if isinstance(data.get("text"), dict):
                message_body = data["text"].get("message", "")
            elif isinstance(data.get("message"), dict):
                message_body = data["message"].get("text") or data["message"].get("body") or ""
            elif "body" in data:
                message_body = data["body"]
            elif "message" in data:
                message_body = data["message"]

            message_body = str(message_body).strip()
            origem = request.args.get("origem", "integra+")

            # Ignora mensagens sem conteúdo
            if not message_body:
                logging.warning(f"⚠️ Ignorando webhook sem mensagem. SID={message_sid}, From={from_number}")
                return jsonify({"status": "ignored", "reason": "empty_message"}), 200

            # Ignora mensagens enviadas pelo próprio bot
            if data.get("fromMe") or data.get("fromApi"):
                logging.info("🛑 Ignorado: mensagem enviada pelo próprio bot (fromMe=True).")
                return jsonify({"status": "ignored", "reason": "sent_by_bot"}), 200

            # Normaliza e processa
            from_number_normalizado = normalizar_para_recebimento(from_number)
            processar_mensagem(from_number_normalizado, message_body, message_sid, origem=origem)

            return jsonify({"status": "success", "origem": origem}), 200

        except Exception as e:
            logging.error(f"❌ Erro no webhook Z-API: {e}", exc_info=True)
            return jsonify({"error": "Erro ao processar webhook Z-API"}), 500


    # --- Fallback para endpoint da IA ---
    @app.route('/api/ia/pending-questions', methods=['GET'])
    def pending_questions():
        return jsonify([]), 200
