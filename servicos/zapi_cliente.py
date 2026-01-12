# ==============================================
# servicos/zapi_cliente.py
# ==============================================
# 📡 Cliente de integração com Z-API (unificado)
# Retorna dict {success: bool, ...}
# ==============================================

import os
import time
import logging
import requests
from database import normalizar_para_envio

log = logging.getLogger(__name__)

ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# Cache simples do status (evita GET antes de cada envio)
_STATUS_CACHE = {"ts": 0, "data": {"online": True, "mensagem": "cache_init"}}
STATUS_TTL_SEC = int(os.getenv("ZAPI_STATUS_TTL_SEC", "30"))  # 30s padrão


def _cfg_ok() -> bool:
    return bool(ZAPI_INSTANCE and ZAPI_TOKEN and ZAPI_CLIENT_TOKEN)


def verificar_status_instancia(force: bool = False) -> dict:
    """
    Consulta o status atual da instância Z-API (com cache).
    """
    global _STATUS_CACHE

    if not _cfg_ok():
        return {"online": False, "mensagem": "⚠️ Variáveis de ambiente Z-API ausentes."}

    now = time.time()
    if (not force) and (now - _STATUS_CACHE["ts"] < STATUS_TTL_SEC):
        return _STATUS_CACHE["data"]

    try:
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/status"
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        r = requests.get(url, headers=headers, timeout=10)

        data = r.json() if r.ok else {}
        online = bool(data.get("connected", False))
        msg = "✅ Instância online" if online else "⚠️ Instância offline ou desconectada"

        _STATUS_CACHE = {"ts": now, "data": {"online": online, "mensagem": msg, "resposta": data}}
        log.info(f"🔎 Status Z-API (cache refresh) → {msg}")
        return _STATUS_CACHE["data"]

    except Exception as e:
        _STATUS_CACHE = {"ts": now, "data": {"online": False, "mensagem": str(e)}}
        log.error(f"❌ Erro ao verificar status da instância Z-API: {e}")
        return _STATUS_CACHE["data"]


def enviar_mensagem(numero_destino: str, corpo_mensagem: str, imagem_url: str = None) -> dict:
    """
    Envia mensagem via Z-API (texto ou imagem).
    Retorna dict com success bool e detalhes.
    """
    if not _cfg_ok():
        msg = "❌ Variáveis de ambiente Z-API ausentes."
        log.error(msg)
        return {"success": False, "erro": msg}

    # Normalização
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
    except Exception as e:
        return {"success": False, "erro": f"Telefone inválido: {e}", "numero": numero_destino}

    tipo_envio = "imagem" if imagem_url else "texto"

    # Checa status (cache)
    st = verificar_status_instancia(force=False)
    if not st.get("online"):
        msg = "⚠️ Instância Z-API offline — envio abortado."
        log.warning(msg)
        return {"success": False, "erro": msg, "status_instancia": st, "numero": numero_normalizado}

    headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}

    if imagem_url:
        payload = {"phone": numero_normalizado, "caption": corpo_mensagem or "", "image": imagem_url}
        endpoint = "send-image"
    else:
        payload = {"phone": numero_normalizado, "message": corpo_mensagem or ""}
        endpoint = "send-text"

    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/{endpoint}"

    try:
        log.info(f"➡️ Z-API SEND | {numero_normalizado} | tipo={tipo_envio} | msg={(corpo_mensagem or '')[:60]}...")
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        body = (r.text or "").strip()

        # Se a instância caiu no meio, invalida cache pra próxima checagem
        low = body.lower()
        if ("instance offline" in low) or ("disconnected" in low):
            verificar_status_instancia(force=True)

        # Falha dura: precisa reconectar/assinar novamente
        if "must subscribe to this instance again" in low:
            return {
                "success": False,
                "status_code": r.status_code,
                "erro": "Z-API exige re-subscrição (instância precisa reconectar no painel).",
                "numero": numero_normalizado,
                "resposta": body[:500],
            }

        success = bool(r.ok) and not any(x in low for x in ["error", "invalid", "failed", "unauthorized"])

        if not success:
            log.error(f"❌ Z-API FAIL ({r.status_code}) → {body[:400]}")
        else:
            log.info(f"✅ Z-API OK → {numero_normalizado}")

        return {
            "success": success,
            "status_code": r.status_code,
            "numero": numero_normalizado,
            "tipo": tipo_envio,
            "resposta": body[:1000],
            "url": url,
        }

    except requests.exceptions.Timeout:
        return {"success": False, "erro": "Timeout na requisição.", "numero": numero_normalizado}

    except Exception as e:
        log.exception(f"💥 Erro inesperado ao enviar via Z-API: {e}")
        return {"success": False, "erro": str(e), "numero": numero_normalizado}
