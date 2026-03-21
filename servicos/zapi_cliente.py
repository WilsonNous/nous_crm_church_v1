# ==============================================
# servicos/zapi_cliente.py
# ==============================================
# 📡 Cliente de integração com Z-API (unificado)
# Retorna dict {success: bool, ...}
# ==============================================

import os
import time
import logging
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, TypedDict
from database import normalizar_para_envio

log = logging.getLogger(__name__)

ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# Cache simples do status (evita GET antes de cada envio)
_STATUS_CACHE = {"ts": 0, "data": {"online": True, "mensagem": "cache_init"}}
_STATUS_CACHE_LOCK = threading.Lock()
STATUS_TTL_SEC = int(os.getenv("ZAPI_STATUS_TTL_SEC", "30"))  # 30s padrão

# Timeouts configuráveis por endpoint
TIMEOUTS = {
    "status": int(os.getenv("ZAPI_TIMEOUT_STATUS", "10")),
    "send-text": int(os.getenv("ZAPI_TIMEOUT_TEXT", "15")),
    "send-image": int(os.getenv("ZAPI_TIMEOUT_IMAGE", "30")),
}


# ==============================================
# Tipagem do retorno
# ==============================================
class ZapiResponse(TypedDict, total=False):
    success: bool
    numero: Optional[str]
    tipo: Optional[str]
    status_code: Optional[int]
    erro: Optional[str]
    resposta: Optional[str]
    status_instancia: Optional[dict]
    url: Optional[str]


# ==============================================
# Helpers
# ==============================================
def _cfg_ok() -> bool:
    """Verifica se todas as variáveis de ambiente estão configuradas."""
    return bool(ZAPI_INSTANCE and ZAPI_TOKEN and ZAPI_CLIENT_TOKEN)


def _create_session() -> requests.Session:
    """Cria sessão HTTP com retry automático para falhas transitórias."""
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    return session


def _parse_json_safe(response: requests.Response) -> dict:
    """Tenta parsear JSON da resposta, retornando dict vazio em caso de erro."""
    if not response.ok or not response.text.strip():
        return {}
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        log.warning(f"Resposta não-JSON da Z-API: {response.text[:200]}")
        return {}


# ==============================================
# Funções públicas
# ==============================================
def verificar_status_instancia(force: bool = False) -> dict:
    """
    Consulta o status atual da instância Z-API (com cache thread-safe).
    """
    global _STATUS_CACHE

    if not _cfg_ok():
        return {"online": False, "mensagem": "⚠️ Variáveis de ambiente Z-API ausentes."}

    now = time.time()

    with _STATUS_CACHE_LOCK:
        # Verifica cache (respeita TTL)
        if (not force) and (now - _STATUS_CACHE["ts"] < STATUS_TTL_SEC):
            return _STATUS_CACHE["data"]

    try:
        # ✅ URL corrigida: sem espaços extras
        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/status"
        headers = {"Client-Token": ZAPI_CLIENT_TOKEN}
        
        session = _create_session()
        r = session.get(url, headers=headers, timeout=TIMEOUTS["status"])

        data = _parse_json_safe(r)
        online = bool(data.get("connected", False))
        msg = "✅ Instância online" if online else "⚠️ Instância offline ou desconectada"

        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE = {
                "ts": now,
                "data": {"online": online, "mensagem": msg, "resposta": data}
            }
        
        log.info(f"🔎 Status Z-API (cache refresh) → {msg}")
        return _STATUS_CACHE["data"]

    except requests.exceptions.Timeout:
        erro_msg = "Timeout ao verificar status da instância Z-API."
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE = {"ts": now, "data": {"online": False, "mensagem": erro_msg}}
        log.error(f"❌ {erro_msg}")
        return _STATUS_CACHE["data"]

    except Exception as e:
        erro_msg = f"Erro ao verificar status da instância Z-API: {e}"
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE = {"ts": now, "data": {"online": False, "mensagem": erro_msg}}
        log.exception(f"❌ {erro_msg}")
        return _STATUS_CACHE["data"]


def enviar_mensagem(
    numero_destino: str,
    corpo_mensagem: str,
    imagem_url: Optional[str] = None
) -> ZapiResponse:
    """
    Envia mensagem via Z-API (texto ou imagem).
    Retorna dict tipado com success bool e detalhes.
    """
    if not _cfg_ok():
        msg = "❌ Variáveis de ambiente Z-API ausentes."
        log.error(msg)
        return {"success": False, "erro": msg}

    # Normalização do número
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
    except Exception as e:
        return {"success": False, "erro": f"Telefone inválido: {e}", "numero": numero_destino}

    tipo_envio = "imagem" if imagem_url else "texto"
    endpoint = "send-image" if imagem_url else "send-text"

    # Checa status da instância (com cache)
    st = verificar_status_instancia(force=False)
    if not st.get("online"):
        msg = "⚠️ Instância Z-API offline — envio abortado."
        log.warning(msg)
        return {
            "success": False,
            "erro": msg,
            "status_instancia": st,
            "numero": numero_normalizado
        }

    headers = {
        "Client-Token": ZAPI_CLIENT_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "phone": numero_normalizado,
        **({"caption": corpo_mensagem or "", "image": imagem_url} if imagem_url else {"message": corpo_mensagem or ""})
    }

    # ✅ URL corrigida: sem espaços extras
    url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/{endpoint}"

    try:
        log.info(
            f"➡️ Z-API SEND | {numero_normalizado} | tipo={tipo_envio} | "
            f"msg={(corpo_mensagem or '')[:60]}{'...' if len(corpo_mensagem or '') > 60 else ''}"
        )

        session = _create_session()
        r = session.post(url, json=payload, headers=headers, timeout=TIMEOUTS[endpoint])
        body = (r.text or "").strip()
        data = _parse_json_safe(r)

        # Se a instância caiu no meio, invalida cache pra próxima checagem
        low = body.lower()
        if ("instance offline" in low) or ("disconnected" in low):
            verificar_status_instancia(force=True)

        # Falha dura: precisa reconectar/assinar novamente
        if "must subscribe to this instance again" in low:
            log.error("❌ Z-API exige re-subscrição da instância.")
            return {
                "success": False,
                "status_code": r.status_code,
                "erro": "Z-API exige re-subscrição (instância precisa reconectar no painel).",
                "numero": numero_normalizado,
                "resposta": body[:500],
            }

        # ✅ Detecção de sucesso mais robusta: HTTP 2xx + campo 'success' ou 'id' na resposta
        success = (
            r.ok and
            isinstance(data, dict) and
            (data.get("success") is True or "id" in data or "messageId" in data)
        )

        if not success:
            log.error(
                f"❌ Z-API FAIL ({r.status_code}) | {numero_normalizado} | "
                f"resposta: {body[:400]}"
            )
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
        log.warning(f"⏱️ Timeout ao enviar mensagem para {numero_normalizado}")
        return {"success": False, "erro": "Timeout na requisição.", "numero": numero_normalizado}

    except requests.exceptions.RequestException as e:
        log.exception(f"💥 Erro de rede ao enviar via Z-API: {e}")
        return {"success": False, "erro": f"Erro de conexão: {e}", "numero": numero_normalizado}

    except Exception as e:
        log.exception(f"💥 Erro inesperado ao enviar via Z-API: {e}")
        return {"success": False, "erro": str(e), "numero": numero_normalizado}
