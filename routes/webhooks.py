import logging
from flask import request, jsonify
from botmsg import processar_mensagem
from database import normalizar_para_recebimento

def register(app):
    # --- Webhook Twilio ---
    @app.route('/api/webhook', methods=['POST'])
    def webhook_twilio():
        try:
            data = request.get_json(silent=True) or request.form

            from_number = data.get('From', '') or data.get('numero', '')
            message_body = data.get('Body', '').strip() if 'Body' in data else data.get('mensagem', '').strip()
            message_sid = data.get('MessageSid', '') or data.get('sid', '')

            # Origem pode vir no body ou querystring → padrão integra+
            origem = data.get('origem') or request.args.get('origem', 'integra+')

            logging.info(
                f"📥 Webhook TWILIO | Origem={origem} | From={from_number} | SID={message_sid} | Msg={message_body}"
            )

            processar_mensagem(from_number, message_body, message_sid, origem=origem)

            return jsonify({"status": "success", "origem": origem}), 200
        except Exception as e:
            logging.error(f"Erro no webhook TWILIO: {e}")
            return jsonify({"error": "Erro ao processar webhook Twilio"}), 500

    # --- Webhook Z-API ---
    @app.route('/api/webhook-zapi', methods=['POST'])
    def webhook_zapi():
        try:
            data = request.get_json() or {}

            from_number = data.get("phone", "")
            message_body = data.get("message", "").strip()
            message_sid = data.get("messageId", None)

            # Origem pode vir na querystring → padrão integra+
            origem = request.args.get("origem", "integra+")

            logging.info(
                f"📥 Webhook Z-API | Origem={origem} | From={from_number} | SID={message_sid} | Msg={message_body}"
            )

            # 🚫 Evita loop infinito: ignora mensagens vazias ou notificações da Z-API
            if not message_body:
                logging.warning(f"⚠️ Ignorando webhook sem mensagem. SID={message_sid}, From={from_number}")
                return jsonify({"status": "ignored", "reason": "empty message"}), 200

            # Normaliza o número de telefone
            from_number_normalizado = normalizar_para_recebimento(from_number)

            # Chama a função de processamento da mensagem
            processar_mensagem(from_number_normalizado, message_body, message_sid, origem=origem)

            return jsonify({"status": "success", "origem": origem}), 200

        except Exception as e:
            logging.error(f"❌ Erro no webhook Z-API: {e}")
            return jsonify({"error": "Erro ao processar webhook Z-API"}), 500
