# ==============================================
# servicos/fila_mensagens.py
# ==============================================
# 📨 Fila unificada de envio de mensagens Z-API
# Usada pelo bot e pelas campanhas (envio sequencial)
# ==============================================

import os
import time
import threading
import logging
from collections import deque
from typing import Any, Tuple, Optional, Callable, Dict

from servicos.zapi_cliente import enviar_mensagem

log = logging.getLogger(__name__)

# =========================
# Config
# =========================
ENVIO_INTERVALO_SEG = float(os.getenv("FILA_ENVIO_INTERVALO_SEG", "2"))   # 2s padrão
RETRY_MAX = int(os.getenv("FILA_RETRY_MAX", "2"))                         # 2 tentativas extra
RETRY_SLEEP_SEG = float(os.getenv("FILA_RETRY_SLEEP_SEG", "3"))           # 3s entre retries

# =========================
# Tipos
# =========================
CallbackFn = Optional[Callable[[Dict[str, Any]], None]]

# item da fila:
# (numero, mensagem, imagem_url, on_success, on_fail, meta)
FilaItem = Tuple[str, str, Optional[str], CallbackFn, CallbackFn, Dict[str, Any]]

# =========================
# Estado da fila
# =========================
fila_mensagens: deque[FilaItem] = deque()
lock = threading.Lock()
_worker_running = False
_worker_thread = None


def _normalizar_para_envio(numero: str) -> str:
    """
    Garante formato 55 + DDD + número (somente dígitos).
    Aceita:
      - "48999999999"
      - "5548999999999"
      - "+55 (48) 99999-9999"
    Retorna:
      - "5548999999999"
    """
    if not numero:
        return ""

    digits = "".join(ch for ch in str(numero) if ch.isdigit())

    # já tem 55 + DDD + 9 + número (13 dígitos)
    if digits.startswith("55") and len(digits) == 13:
        return digits

    # veio 11 dígitos (DDD + 9 + número)
    if len(digits) == 11:
        return "55" + digits

    # veio 10 dígitos (DDD + número sem 9) -> tenta corrigir
    if len(digits) == 10:
        return "55" + digits[:2] + "9" + digits[2:]

    # fallback: devolve como está (melhor logar do que explodir)
    return digits


def _parse_result(res: Any) -> Tuple[bool, str, int]:
    """
    Normaliza o retorno do enviar_mensagem:
      - se vier bool, usa direto
      - se vier dict, lê success / erro / resposta / status_code
    Retorna: (ok, err_text, status_code)
    """
    if isinstance(res, bool):
        return res, "" if res else "retorno_false", 0

    if isinstance(res, dict):
        ok = bool(res.get("success", False))
        status_code = int(res.get("status_code") or 0)

        err_text = ""
        if res.get("erro"):
            err_text = str(res.get("erro"))
        elif res.get("error"):
            err_text = str(res.get("error"))
        elif res.get("resposta"):
            err_text = str(res.get("resposta"))
        else:
            err_text = "" if ok else "retorno_sem_detalhes"

        return ok, err_text, status_code

    ok = bool(res)
    return ok, "" if ok else f"retorno_tipo_inesperado={type(res)}", 0


def _should_retry(err_text: str, status_code: int = 0) -> bool:
    """
    Define se vale tentar novamente.
    - Retry: timeouts, 429, 5xx, erros transitórios
    - NÃO retry: "must subscribe again", unauthorized, invalid phone etc.
    """
    t = (err_text or "").lower()

    # falhas que NÃO adianta insistir
    if any(x in t for x in [
        "must subscribe to this instance again",
        "subscribe to this instance again",
        "unauthorized",
        "invalid phone",
        "telefone inválido",
        "número inválido",
        "token inválido",
        "expired",
    ]):
        return False

    # por status_code (se vier)
    if status_code in (429, 500, 502, 503, 504):
        return True

    # por texto
    return any(x in t for x in [
        "timeout",
        "timed out",
        "too many requests",
        "temporarily",
        "try again",
        "server error",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "rate limit",
        "connection reset",
        "connection aborted",
        "read timed out",
    ])


def _safe_call(cb: CallbackFn, payload: Dict[str, Any]) -> None:
    """Executa callback sem deixar quebrar o worker."""
    if not callable(cb):
        return
    try:
        cb(payload)
    except Exception as e:
        log.error(f"❌ Erro no callback da fila: {e}")


def _processar_fila_worker():
    global _worker_running

    log.info("🧵 Worker da fila iniciado.")
    enviados_ok = 0
    falhas = 0

    while True:
        with lock:
            if not fila_mensagens:
                _worker_running = False
                log.info(f"✅ Fila vazia. Worker encerrando. OK={enviados_ok} | Falhas={falhas}")
                return

            numero, mensagem, imagem_url, on_success, on_fail, meta = fila_mensagens.popleft()
            restante = len(fila_mensagens)

        numero_envio = _normalizar_para_envio(numero)

        if not numero_envio:
            falhas += 1
            log.warning("⚠️ Item sem número válido. Ignorando.")
            _safe_call(on_fail, {
                "ok": False,
                "numero": numero,
                "numero_envio": numero_envio,
                "status_code": 0,
                "erro": "numero_invalido",
                "mensagem": mensagem,
                "imagem_url": imagem_url,
                "meta": meta
            })
            continue

        ok = False
        last_err = ""
        last_code = 0
        last_res: Any = None

        # Tentativas (1 + RETRY_MAX)
        max_tentativas = RETRY_MAX + 1
        for tentativa in range(1, max_tentativas + 1):
            try:
                last_res = enviar_mensagem(numero_envio, mensagem, imagem_url)
                ok, last_err, last_code = _parse_result(last_res)

                if ok:
                    break

            except Exception as e:
                ok = False
                last_err = str(e)
                last_code = 0
                last_res = None

            if tentativa < max_tentativas and _should_retry(last_err, last_code):
                log.warning(
                    f"🔁 Retry {tentativa}/{max_tentativas} → {numero_envio} | "
                    f"code={last_code} | motivo={last_err[:160]}"
                )
                time.sleep(RETRY_SLEEP_SEG)
            else:
                break

        if ok:
            enviados_ok += 1
            status = "✅"
        else:
            falhas += 1
            status = "❌"

        msg_preview = (mensagem or "").replace("\n", " ")[:60]
        err_preview = (last_err or "").replace("\n", " ")[:180]

        log.info(
            f"{status} Fila → {numero_envio} | {msg_preview}... | "
            f"code={last_code} | err={err_preview} | restante={restante}"
        )

        payload = {
            "ok": ok,
            "numero": numero,
            "numero_envio": numero_envio,
            "status_code": last_code,
            "erro": last_err,
            "mensagem": mensagem,
            "imagem_url": imagem_url,
            "res": last_res,   # retorno bruto (dict/bool)
            "meta": meta
        }

        if ok:
            _safe_call(on_success, payload)
        else:
            _safe_call(on_fail, payload)

        time.sleep(ENVIO_INTERVALO_SEG)


def adicionar_na_fila(
    numero: str,
    mensagem: str,
    imagem_url: str = None,
    on_success: CallbackFn = None,
    on_fail: CallbackFn = None,
    meta: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Adiciona mensagem na fila e garante que existe um worker rodando.
    Callbacks:
      - on_success(payload): chamado quando a Z-API confirmou envio
      - on_fail(payload): chamado quando falhou (sem retry ou após esgotar tentativas)

    meta: dict livre (ex.: {"origem":"campanha","visitante_id":1,"evento":"X"})
    """
    global _worker_running, _worker_thread

    try:
        if meta is None:
            meta = {}

        with lock:
            fila_mensagens.append((numero, mensagem, imagem_url, on_success, on_fail, meta))
            tam = len(fila_mensagens)

            if not _worker_running:
                _worker_running = True
                _worker_thread = threading.Thread(target=_processar_fila_worker, daemon=True)
                _worker_thread.start()
                log.info(f"🚀 Worker disparado. Tamanho atual da fila={tam}")
            else:
                log.info(f"➕ Item adicionado na fila. Tamanho atual da fila={tam}")

        return True

    except Exception as e:
        log.error(f"❌ Falha ao enfileirar: {e}")
        return False


# ✅ Alias para compatibilidade com versões antigas
enviar_mensagem_para_fila = adicionar_na_fila
