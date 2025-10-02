import logging
from flask import request, jsonify
from botmsg import processar_mensagem

def register(app):
    @app.route('/api/webhook', methods=['POST'])
    def webhook():
        try:
            data = request.get_json(silent=True) or request.form
            from_number = data.get('From', '') or data.get('numero', '')
            message_body = data.get('Body', '').strip() if 'Body' in data else data.get('mensagem', '').strip()
            message_sid = data.get('MessageSid', '') or data.get('sid', '')
            origem = data.get('origem') or request.args.get('origem', 'integra+')
            logging.info(f"📥 Webhook recebido | Origem={origem} | From={from_number} | SID={message_sid} | Msg={message_body}")
            processar_mensagem(from_number, message_body, message_sid, origem=origem)
            return jsonify({"status": "success", "origem": origem}), 200
        except Exception as e:
            logging.error(f"Erro no webhook: {e}")
            return jsonify({"error": "Erro ao processar webhook"}), 500

