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
from servicos.zapi_cliente import enviar_mensagem

# =========================
# Config
# =========================
ENVIO_INTERVALO_SEG = float(os.getenv("FILA_ENVIO_INTERVALO_SEG", "2"))  # 2s padrão
RETRY_MAX = int(os.getenv("FILA_RETRY_MAX", "2"))                         # 2 tentativas extra
RETRY_SLEEP_SEG = float(os.getenv("FILA_RETRY_SLEEP_SEG", "3"))           # 3s entre retries

# =========================
# Estado da fila
# =========================
fila_mensagens = deque()
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
        # adiciona '9' após DDD
        return "55" + digits[:2] + "9" + digits[2:]

    # fallback: devolve como está (melhor logar do que explodir)
    return digits


def _should_retry(err_text: str) -> bool:
    """
    Define se vale tentar novamente.
    Ajuste conforme teu retorno real da Z-API.
    """
    if not err_text:
        return False
    t = err_text.lower()
    return any(x in t for x in [
        "timeout",
        "timed out",
        "429",
        "too many requests",
        "temporarily",
        "try again",
        "server error",
        "502",
        "503",
        "504",
    ])


def _processar_fila_worker():
    global _worker_running

    logging.info("🧵 Worker da fila iniciado.")
    enviados_total = 0

    while True:
        with lock:
            if not fila_mensagens:
                _worker_running = False
                logging.info(f"✅ Fila vazia. Worker encerrando. Total enviados nesta rodada: {enviados_total}")
                return

            numero, mensagem, imagem_url = fila_mensagens.popleft()
            restante = len(fila_mensagens)

        numero_envio = _normalizar_para_envio(numero)

        # Segurança mínima
        if not numero_envio:
            logging.warning("⚠️ Item sem número. Ignorando.")
            continue

        # Tentativas (retry)
        ok = False
        last_err = ""
        for tentativa in range(1, RETRY_MAX + 2):  # ex: 1 + 2 retries = 3 tentativas
            try:
                ok = enviar_mensagem(numero_envio, mensagem, imagem_url)
                if ok:
                    break
                last_err = "retorno_false"
            except Exception as e:
                last_err = str(e)

            # retry?
            if tentativa < (RETRY_MAX + 2) and _should_retry(last_err):
                logging.warning(f"🔁 Retry {tentativa}/{RETRY_MAX+1} → {numero_envio} | motivo={last_err}")
                time.sleep(RETRY_SLEEP_SEG)
            else:
                break

        status = "✅" if ok else "❌"
        enviados_total += 1 if ok else 0

        logging.info(
            f"{status} Fila → {numero_envio} | "
            f"{(mensagem or '')[:60].replace('\\n',' ')}... | "
            f"restante={restante}"
        )

        time.sleep(ENVIO_INTERVALO_SEG)


def adicionar_na_fila(numero: str, mensagem: str, imagem_url: str = None) -> bool:
    """
    Adiciona mensagem na fila e garante que existe um worker rodando.
    Retorna True se enfileirou.
    """
    global _worker_running, _worker_thread

    try:
        with lock:
            fila_mensagens.append((numero, mensagem, imagem_url))
            tam = len(fila_mensagens)

            # Se não tem worker rodando, inicia
            if not _worker_running:
                _worker_running = True
                _worker_thread = threading.Thread(target=_processar_fila_worker, daemon=True)
                _worker_thread.start()
                logging.info(f"🚀 Worker disparado. Tamanho atual da fila={tam}")
            else:
                logging.info(f"➕ Item adicionado na fila. Tamanho atual da fila={tam}")

        return True

    except Exception as e:
        logging.error(f"❌ Falha ao enfileirar: {e}")
        return False


# ✅ Alias para compatibilidade com versões antigas
enviar_mensagem_para_fila = adicionar_na_fila
