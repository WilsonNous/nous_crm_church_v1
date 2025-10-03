import os
import logging
import requests
from database import normalizar_para_envio

# 🔄 Configurações Z-API (carregadas do ambiente)
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

def enviar_mensagem(numero_destino: str, corpo_mensagem: str, imagem_url: str = None):
    """
    Envia mensagem de texto ou imagem via Z-API
    """
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
        headers = {
            "Client-Token": ZAPI_CLIENT_TOKEN,
            "Content-Type": "application/json"
        }

        if imagem_url:
            payload = {
                "phone": numero_normalizado,
                "caption": corpo_mensagem,
                "image": imagem_url
            }
            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
        else:
            payload = {
                "phone": numero_normalizado,
                "message": corpo_mensagem
            }
            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

        logging.info(f"➡️ Enviando via Z-API | {numero_normalizado} | {corpo_mensagem[:50]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if not response.ok:
            logging.error(f"❌ Falha no envio para {numero_normalizado}: {response.status_code} {response.text}")
        else:
            logging.info(f"✅ Mensagem enviada para {numero_normalizado}")

    except Exception as e:
        logging.error(f"Erro ao enviar mensagem via Z-API: {e}")

def enviar_mensagem_manual(numero_destino: str, titulo: str, params: dict):
    """
    Envia mensagem formatada manualmente via Z-API (substitui template do Twilio).
    Exemplo:
      enviar_mensagem_manual("48999999999", "Dados de Contato", {"Nome": "João", "Idade": "30"})
    """
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)

        # Monta a mensagem com título + parâmetros
        msg = f"📌 {titulo}\n\n"
        for k, v in params.items():
            msg += f"- {k.capitalize()}: {v}\n"

        enviar_mensagem(numero_normalizado, msg)
        logging.info(f"✅ Mensagem manual enviada para {numero_normalizado}")

    except Exception as e:
        logging.error(f"Erro ao enviar mensagem manual via Z-API: {e}")

