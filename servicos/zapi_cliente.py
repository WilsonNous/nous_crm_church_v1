# ==============================================
# servicos/zapi_cliente.py
# ==============================================
# 📡 Cliente de integração com Z-API (unificado)
# Função: enviar mensagens de texto ou imagem via API oficial Z-API
# Registro de conversa é feito pelo módulo chamador (ex: campanha ou bot)
# ==============================================

import os
import logging
import requests
from datetime import datetime
from database import normalizar_para_envio

# ================================================================
# 🪵 Configuração global de logging
# ================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S"
)

# ================================================================
# 🔧 Configurações Z-API (carregadas do ambiente)
# ================================================================
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# ================================================================
# 🔍 Verificar Status da Instância Z-API
# ================================================================
def verificar_status_instancia() -> dict:
    """
    Consulta o status atual da instância Z-API.
    Retorna um dicionário com status e detalhes.
    """
    try:
        if not (ZAPI_INSTANCE and ZAPI_TOKEN):
            return {"online": False, "mensagem": "⚠️ Variáveis de ambiente Z-API ausentes."}

        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/status"
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json() if response.ok else {}

        online = bool(data.get("connected", False))
        mensagem = "✅ Instância online" if online else "⚠️ Instância offline ou desconectada"

        logging.info(f"🔎 Status Z-API → {mensagem}")
        return {"online": online, "mensagem": mensagem, "resposta": data}

    except Exception as e:
        logging.error(f"❌ Erro ao verificar status da instância Z-API: {e}")
        return {"online": False, "mensagem": str(e)}


# ================================================================
# 🚀 Enviar Mensagem via Z-API
# ================================================================
def enviar_mensagem(numero_destino: str, corpo_mensagem: str, imagem_url: str = None) -> dict:
    """
    Envia mensagem via Z-API (texto ou imagem).
    Retorna um dicionário detalhado com resultado.
    """
    try:
        # -------------------------------
        # 🧩 Verificações iniciais
        # -------------------------------
        if not (ZAPI_INSTANCE and ZAPI_TOKEN and ZAPI_CLIENT_TOKEN):
            msg = "❌ Falha: Variáveis de ambiente Z-API ausentes."
            logging.error(msg)
            return {"success": False, "erro": msg}

        numero_normalizado = normalizar_para_envio(numero_destino)
        tipo_envio = "imagem" if imagem_url else "texto"

        # -------------------------------
        # 🩺 Valida instância antes do envio
        # -------------------------------
        status = verificar_status_instancia()
        if not status["online"]:
            msg = "⚠️ Instância Z-API está offline — envio abortado."
            logging.warning(msg)
            return {"success": False, "erro": msg, "status_instancia": status}

        # -------------------------------
        # 🧾 Monta headers e payload
        # -------------------------------
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
            endpoint = "send-image"
        else:
            payload = {
                "phone": numero_normalizado,
                "message": corpo_mensagem
            }
            endpoint = "send-text"

        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/{endpoint}"

        logging.info(f"➡️ Enviando via Z-API | {numero_normalizado} | Tipo={tipo_envio} | Msg={corpo_mensagem[:60]}...")

        # -------------------------------
        # 🌐 Envio HTTP
        # -------------------------------
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        texto_retorno = response.text.strip()

        logging.info(f"📨 Retorno Z-API ({response.status_code}): {texto_retorno[:400]}")

        # -------------------------------
        # 🧠 Interpretação do resultado
        # -------------------------------
        sucesso = response.ok and not any(
            kw in texto_retorno.lower()
            for kw in ["error", "invalid", "offline", "failed", "unauthorized"]
        )

        if not sucesso:
            if "instance offline" in texto_retorno.lower():
                logging.error(f"⚠️ Instância Z-API OFFLINE. Verifique conexão no painel.")
            elif "invalid phone" in texto_retorno.lower():
                logging.error(f"⚠️ Número inválido: {numero_normalizado}")
            elif "unauthorized" in texto_retorno.lower():
                logging.error("🔐 Token Z-API inválido ou expirado.")
            else:
                logging.error(f"❌ Falha no envio ({response.status_code}): {texto_retorno}")
        else:
            logging.info(f"✅ Envio confirmado pela Z-API para {numero_normalizado}")

        # -------------------------------
        # 📦 Retorno estruturado
        # -------------------------------
        return {
            "success": sucesso,
            "status_code": response.status_code,
            "numero": numero_normalizado,
            "mensagem": corpo_mensagem,
            "tipo": tipo_envio,
            "url": url,
            "resposta": texto_retorno,
            "status_instancia": status
        }

    except requests.exceptions.Timeout:
        logging.error(f"⏱️ Timeout ao enviar mensagem para {numero_destino}.")
        return {"success": False, "erro": "Timeout na requisição."}

    except Exception as e:
        logging.exception(f"💥 Erro inesperado ao enviar via Z-API: {e}")
        return {"success": False, "erro": str(e)}
