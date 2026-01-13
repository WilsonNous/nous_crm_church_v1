# ==============================================
# servicos/fila_mensagens.py  (VERSÃO DB QUEUE)
# ==============================================
# 📨 Fila unificada de envio de mensagens Z-API
# Persistida no MySQL (não perde com restart do Gunicorn)
# Usada pelo bot e pelas campanhas (envio sequencial)
# ==============================================

import os
import time
import json
import threading
import logging
from contextlib import closing
from typing import Any, Tuple, Optional, Callable, Dict, List

import database
from database import get_db_connection, salvar_conversa
from servicos.zapi_cliente import enviar_mensagem

log = logging.getLogger(__name__)

# =========================
# Config
# =========================
ENVIO_INTERVALO_SEG = float(os.getenv("FILA_ENVIO_INTERVALO_SEG", "2"))   # 2s padrão
RETRY_MAX = int(os.getenv("FILA_RETRY_MAX", "2"))                         # 2 tentativas extra
RETRY_SLEEP_SEG = float(os.getenv("FILA_RETRY_SLEEP_SEG", "3"))           # 3s entre retries

POLL_SECONDS = float(os.getenv("FILA_POLL_SECONDS", "1"))                 # 1s
BATCH_SIZE = int(os.getenv("FILA_BATCH_SIZE", "20"))                      # 20

MAX_ATTEMPTS = 1 + RETRY_MAX  # total de tentativas = 1 + retries

# =========================
# Tipos
# =========================
CallbackFn = Optional[Callable[[Dict[str, Any]], None]]

# =========================
# Worker
# =========================
_lock = threading.Lock()
_worker_running = False
_worker_thread = None


def _digits(s: Any) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


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

    digits = _digits(numero)

    # já tem 55 + DDD + 9 + número (13 dígitos)
    if digits.startswith("55") and len(digits) == 13:
        return digits

    # veio 11 dígitos (DDD + 9 + número)
    if len(digits) == 11:
        return "55" + digits

    # veio 10 dígitos (DDD + número sem 9) -> tenta corrigir
    if len(digits) == 10:
        return "55" + digits[:2] + "9" + digits[2:]

    # fallback
    return digits


def _normalizar_para_salvar_no_banco(telefone_envio: str) -> str:
    """
    Para salvar em conversas/visitantes:
    - remove 55 se existir
    - mantém apenas dígitos
    Retorna DDD + 9 + número (11 dígitos) quando possível.
    """
    d = _digits(telefone_envio)
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    return d


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
    - NÃO retry: subscribe again, unauthorized, invalid phone etc.
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
    if not callable(cb):
        return
    try:
        cb(payload)
    except Exception as e:
        log.error(f"❌ Erro no callback da fila: {e}")


# =========================
# DB helpers
# =========================

def _db_insert_item(numero_envio: str, mensagem: str, imagem_url: Optional[str], meta: Dict[str, Any]) -> bool:
    try:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fila_envios (numero, mensagem, imagem_url, status, tentativas, meta_json)
                VALUES (%s, %s, %s, 'pendente', 0, %s)
            """, (numero_envio, mensagem, imagem_url, meta_json))
            conn.commit()
            return True
    except Exception as e:
        log.error(f"❌ Falha ao gravar item na fila_envios: {e}")
        return False


def _db_claim_batch(limit: int) -> List[Dict[str, Any]]:
    """
    Pega um lote de pendentes e marca como 'processando' de forma transacional.
    Usa FOR UPDATE para evitar dois workers pegarem o mesmo item em cenários com múltiplos processos.
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []

            cur = conn.cursor()
            conn.begin()

            cur.execute("""
                SELECT id, numero, mensagem, imagem_url, tentativas, meta_json
                FROM fila_envios
                WHERE status = 'pendente'
                ORDER BY created_at ASC
                LIMIT %s
                FOR UPDATE
            """, (limit,))
            rows = cur.fetchall() or []

            if not rows:
                conn.commit()
                return []

            ids = [r["id"] for r in rows]

            cur.execute(
                f"""
                UPDATE fila_envios
                SET status='processando'
                WHERE status='pendente'
                  AND id IN ({','.join(['%s'] * len(ids))})
                """,
                tuple(ids)
            )

            conn.commit()
            return rows

    except Exception as e:
        log.error(f"❌ Erro ao buscar/claim batch da fila_envios: {e}")
        return []


def _db_mark_success(envio_id: int, status_code: int = 200) -> None:
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return
            cur = conn.cursor()
            cur.execute("""
                UPDATE fila_envios
                SET status='enviado', status_code=%s, last_error=NULL
                WHERE id=%s
            """, (int(status_code or 0), envio_id))
            conn.commit()
    except Exception as e:
        log.error(f"❌ Erro ao marcar sucesso envio_id={envio_id}: {e}")


def _db_mark_fail_or_retry(envio_id: int, next_attempt_count: int, status_code: int, err: str) -> str:
    """
    next_attempt_count = tentativas + 1 (ou seja, a contagem após esta tentativa)
    Retorna novo status: 'pendente' (retry) ou 'falha' (final)
    """
    err = (err or "")[:480]
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return "falha"

            cur = conn.cursor()

            allow_retry = (next_attempt_count < MAX_ATTEMPTS) and _should_retry(err, int(status_code or 0))
            novo_status = "pendente" if allow_retry else "falha"

            cur.execute("""
                UPDATE fila_envios
                SET status=%s, tentativas=%s, status_code=%s, last_error=%s
                WHERE id=%s
            """, (novo_status, int(next_attempt_count), int(status_code or 0), err, envio_id))
            conn.commit()
            return novo_status

    except Exception as e:
        log.error(f"❌ Erro ao marcar falha/retry envio_id={envio_id}: {e}")
        return "falha"


# =========================
# Pós-envio: campanha (confirma no CRM)
# =========================

def _pos_envio_sucesso(meta: Dict[str, Any], mensagem: str, numero_envio: str) -> None:
    """
    - salva conversa como enviada
    - marca eventos_envios como enviado
    """
    try:
        visitante_id = meta.get("visitante_id")
        evento_nome = meta.get("evento")
        origem = meta.get("origem", "campanha")

        if not visitante_id or not evento_nome:
            return  # não é campanha, ou não tem info suficiente

        # telefone para salvar na tabela conversas (normalmente sem 55)
        telefone_raw = meta.get("telefone_raw") or _normalizar_para_salvar_no_banco(numero_envio)
        telefone_db = _normalizar_para_salvar_no_banco(telefone_raw)

        # 1) conversa
        salvar_conversa(
            numero=telefone_db,
            mensagem=mensagem,
            tipo="enviada",
            sid=None,
            origem=origem
        )

        # 2) status do envio
        database.atualizar_status_envio_evento(int(visitante_id), str(evento_nome), "enviado")

    except Exception as e:
        log.error(f"❌ Pós-envio sucesso (campanha) falhou: {e}")


def _pos_envio_falha_final(meta: Dict[str, Any]) -> None:
    """
    Marca eventos_envios como falha quando for falha final.
    """
    try:
        visitante_id = meta.get("visitante_id")
        evento_nome = meta.get("evento")
        if not visitante_id or not evento_nome:
            return
        database.atualizar_status_envio_evento(int(visitante_id), str(evento_nome), "falha")
    except Exception as e:
        log.error(f"❌ Pós-envio falha final (campanha) falhou: {e}")


# =========================
# Worker loop
# =========================

def _processar_fila_worker():
    global _worker_running

    log.info("🧵 Worker DB-Queue iniciado.")

    while True:
        with _lock:
            if not _worker_running:
                log.info("🛑 Worker DB-Queue finalizado (flag).")
                return

        itens = _db_claim_batch(BATCH_SIZE)
        if not itens:
            time.sleep(POLL_SECONDS)
            continue

        for item in itens:
            envio_id = item["id"]
            numero = item["numero"]
            mensagem = item["mensagem"]
            imagem_url = item.get("imagem_url")
            tentativas_atual = int(item.get("tentativas") or 0)

            meta = {}
            try:
                if item.get("meta_json"):
                    meta = json.loads(item["meta_json"]) if isinstance(item["meta_json"], str) else (item["meta_json"] or {})
            except Exception:
                meta = {}

            # valida número
            numero_envio = _normalizar_para_envio(numero)
            if not numero_envio:
                novo_status = _db_mark_fail_or_retry(envio_id, tentativas_atual + 1, 0, "numero_invalido")
                if novo_status == "falha":
                    _pos_envio_falha_final(meta)
                log.warning(f"⚠️ envio_id={envio_id} número inválido. status={novo_status}")
                continue

            ok = False
            last_err = ""
            last_code = 0
            last_res: Any = None

            # 1 tentativa agora (retry volta pra pendente)
            try:
                last_res = enviar_mensagem(numero_envio, mensagem, imagem_url)
                ok, last_err, last_code = _parse_result(last_res)
            except Exception as e:
                ok = False
                last_err = str(e)
                last_code = 0
                last_res = None

            msg_preview = (mensagem or "").replace("\n", " ")[:60]
            err_preview = (last_err or "").replace("\n", " ")[:180]

            payload = {
                "ok": ok,
                "numero": numero,
                "numero_envio": numero_envio,
                "status_code": last_code,
                "erro": last_err,
                "mensagem": mensagem,
                "imagem_url": imagem_url,
                "res": last_res,
                "meta": meta,
                "envio_id": envio_id
            }

            # callbacks opcionais (não use em DB Queue)
            on_success = meta.get("_on_success_cb")
            on_fail = meta.get("_on_fail_cb")

            if ok:
                _db_mark_success(envio_id, last_code)
                _pos_envio_sucesso(meta, mensagem, numero_envio)

                log.info(f"✅ Fila(DB) → {numero_envio} | {msg_preview}... | code={last_code} | envio_id={envio_id}")
                _safe_call(on_success, payload)

            else:
                novo_status = _db_mark_fail_or_retry(envio_id, tentativas_atual + 1, last_code, last_err)

                if novo_status == "pendente":
                    log.warning(f"🔁 Retry agendado → envio_id={envio_id} | {numero_envio} | code={last_code} | err={err_preview}")
                    time.sleep(RETRY_SLEEP_SEG)
                else:
                    _pos_envio_falha_final(meta)
                    log.error(f"❌ Falha final → envio_id={envio_id} | {numero_envio} | code={last_code} | err={err_preview}")
                    _safe_call(on_fail, payload)

            time.sleep(ENVIO_INTERVALO_SEG)


def iniciar_worker() -> None:
    global _worker_running, _worker_thread
    with _lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_running = True
        _worker_thread = threading.Thread(target=_processar_fila_worker, daemon=True)
        _worker_thread.start()
        log.info("🚀 Worker DB-Queue ligado.")


def parar_worker() -> None:
    global _worker_running
    with _lock:
        _worker_running = False


# =========================
# API pública (mantém compatibilidade)
# =========================

def adicionar_na_fila(
    numero: str,
    mensagem: str,
    imagem_url: str = None,
    on_success: CallbackFn = None,
    on_fail: CallbackFn = None,
    meta: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Adiciona mensagem na fila (MySQL) e garante que existe um worker rodando.

    IMPORTANTE:
    - on_success/on_fail aqui não são ideais em DB Queue (porque o callback não existe após restart).
    - Se você precisa ação pós-envio, grave isso no DB (status) e use tela/consulta.
    """
    try:
        if meta is None:
            meta = {}

        numero_envio = _normalizar_para_envio(numero)
        if not numero_envio:
            log.warning("⚠️ Tentativa de enfileirar com número inválido.")
            return False

        # NÃO recomendo persistir callbacks no DB (fica só comentado)
        # meta["_on_success_cb"] = on_success
        # meta["_on_fail_cb"] = on_fail

        ok = _db_insert_item(numero_envio, mensagem, imagem_url, meta)
        if not ok:
            return False

        iniciar_worker()
        return True

    except Exception as e:
        log.error(f"❌ Falha ao enfileirar (DB Queue): {e}")
        return False


# ✅ Alias para compatibilidade com versões antigas
enviar_mensagem_para_fila = adicionar_na_fila
