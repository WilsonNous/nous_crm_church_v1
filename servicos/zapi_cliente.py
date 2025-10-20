# ==============================================
# servicos/zapi_cliente.py
# ==============================================
# 📡 Cliente de integração com Z-API (unificado)
# Agora registra histórico de mensagens enviadas.
# ==============================================

import os
import logging
import requests
from datetime import datetime
from database import normalizar_para_envio, salvar_log_whatsapp

# 🔄 Configurações Z-API (carregadas do ambiente)
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

def enviar_mensagem(numero_destino: str, corpo_mensagem: str, imagem_url: str = None) -> bool:
    """
    Envia mensagem de texto ou imagem via Z-API.
    Retorna True se o envio foi bem-sucedido, False caso contrário.
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
            return False

        # ✅ Registro no histórico de mensagens
        salvar_log_whatsapp(
            telefone=numero_normalizado,
            mensagem=corpo_mensagem,
            direcao="enviada",
            origem="campanha" if "campanha" in corpo_mensagem.lower() else "bot",
            data_envio=datetime.now()
        )

        logging.info(f"✅ Mensagem enviada e registrada para {numero_normalizado}")
        return True

    except Exception as e:
        logging.error(f"Erro ao enviar mensagem via Z-API: {e}")
        return False
