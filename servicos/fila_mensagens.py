# ==============================================
# servicos/fila_mensagens.py  (VERSÃO DB QUEUE + ANTI-SPAM + IS_REPLY)
# ==============================================
# 📨 Fila unificada de envio de mensagens Z-API
# Persistida no MySQL + Proteções anti-spam
# Suporta is_reply para respostas conversacionais
# Usada pelo bot e pelas campanhas (envio sequencial)
# ==============================================

import os
import time
import json
import threading
import logging
from contextlib import closing
from datetime import datetime
from typing import Any, Tuple, Optional, Callable, Dict, List

import database
from database import get_db_connection, salvar_conversa
from servicos.zapi_cliente import enviar_mensagem
from servicos.anti_spam_controller import AntiSpamController

log = logging.getLogger(__name__)

# =========================
# Config
# =========================
ENVIO_INTERVALO_SEG = float(os.getenv("FILA_ENVIO_INTERVALO_SEG", "2"))
RETRY_MAX = int(os.getenv("FILA_RETRY_MAX", "2"))
RETRY_SLEEP_SEG = float(os.getenv("FILA_RETRY_SLEEP_SEG", "3"))

POLL_SECONDS = float(os.getenv("FILA_POLL_SECONDS", "1"))
BATCH_SIZE = int(os.getenv("FILA_BATCH_SIZE", "20"))

MAX_ATTEMPTS = 1 + RETRY_MAX

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
_anti_spam: Optional[AntiSpamController] = None  # Instância do controller anti-spam


def _digits(s: Any) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def _normalizar_para_envio(numero: str) -> str:
    """
    Garante formato 55 + DDD + número (somente dígitos).
    """
    if not numero:
        return ""

    digits = _digits(numero)

    if digits.startswith("55") and len(digits) == 13:
        return digits
    if len(digits) == 11:
        return "55" + digits
    if len(digits) == 10:
        return "55" + digits[:2] + "9" + digits[2:]
    return digits


def _normalizar_para_salvar_no_banco(telefone_envio: str) -> str:
    """
    Para salvar em conversas/visitantes: remove 55, mantém dígitos.
    Retorna DDD + 9 + número (11 dígitos) quando possível.
    """
    d = _digits(telefone_envio)
    if d.startswith("55") and len(d) >= 12:
        d = d[2:]
    return d


def _parse_result(res: Any) -> Tuple[bool, str, int]:
    """Normaliza o retorno do enviar_mensagem."""
    if isinstance(res, bool):
        return res, "" if res else "retorno_false", 0

    if isinstance(res, dict):
        ok = bool(res.get("success", False))
        status_code = int(res.get("status_code") or 0)
        err_text = str(res.get("erro") or res.get("error") or res.get("resposta") or ("retorno_sem_detalhes" if not ok else ""))
        return ok, err_text, status_code

    ok = bool(res)
    return ok, "" if ok else f"retorno_tipo_inesperado={type(res)}", 0


def _should_retry(err_text: str, status_code: int = 0) -> bool:
    """Define se vale tentar novamente."""
    t = (err_text or "").lower()
    if any(x in t for x in [
        "must subscribe to this instance again", "subscribe to this instance again",
        "unauthorized", "invalid phone", "telefone inválido", "número inválido",
        "token inválido", "expired",
    ]):
        return False
    if status_code in (429, 500, 502, 503, 504):
        return True
    return any(x in t for x in [
        "timeout", "timed out", "too many requests", "temporarily", "try again",
        "server error", "bad gateway", "service unavailable", "gateway timeout",
        "rate limit", "connection reset", "connection aborted", "read timed out",
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
    """Pega lote de pendentes com lock transacional."""
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
            placeholders = ','.join(['%s'] * len(ids))
            cur.execute(
                f"UPDATE fila_envios SET status='processando' WHERE status='pendente' AND id IN ({placeholders})",
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


def _db_reequeue_item(envio_id: int, scheduled_for: datetime) -> bool:
    """Re-agenda item para horário futuro (fora do horário comercial)."""
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return False
            cur = conn.cursor()
            cur.execute("""
                UPDATE fila_envios
                SET status='pendente', scheduled_for=%s
                WHERE id=%s
            """, (scheduled_for, envio_id))
            conn.commit()
            return True
    except Exception as e:
        log.error(f"❌ Erro ao re-agendar envio_id={envio_id}: {e}")
        return False


# =========================
# 🛡️ Anti-Spam: Verificação e Delay (com is_reply)
# =========================

def _check_anti_spam_and_sleep(envio_id: int, numero: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verifica anti-spam antes do envio.
    
    Args:
        envio_id: ID do envio na fila
        numero: Número do destinatário
        meta: Metadados do envio (contém is_reply)
    
    Returns:
        Tuple[bool, str]: (pode_enviar, motivo)
        Se não puder e for reequeue, re-agenda o item e retorna False.
    """
    global _anti_spam
    if not _anti_spam:
        return True, "ok"  # Fallback se controller não estiver inicializado

    # Extrai is_reply do meta (padrão: False para compatibilidade)
    is_reply = meta.get("is_reply", False)
    
    can_send, reason = _anti_spam.can_send_now(is_reply=is_reply)
    
    if not can_send:
        if reason.startswith("reequeue:"):
            # Re-agendar para horário permitido
            _, next_time_iso = reason.split(":", 1)
            try:
                next_time = datetime.fromisoformat(next_time_iso)
                if _db_reequeue_item(envio_id, next_time):
                    log.info(f"⏰ Re-agendado envio_id={envio_id} para {next_time} | motivo: {reason}")
                    return False, f"reequeued:{next_time}"
            except Exception as e:
                log.error(f"❌ Falha ao re-agendar envio_id={envio_id}: {e}")
        else:
            log.info(f"⏸️ Aguardando anti-spam: {reason} | envio_id={envio_id} | reply={is_reply}")
            time.sleep(5)  # Pequena pausa antes de reavaliar
    
    return can_send, reason


# =========================
# 🐛 Debug: Status "INICIO" (CORRIGIDO para PyMySQL)
# =========================

def _debug_status_update(meta: Dict[str, Any], telefone_db: str, origem: str, etapa: str):
    """
    Log de debug para investigar falha no update do status.
    ✅ Corrigido: usa cursor() sem dictionary=True (compatível com PyMySQL)
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                log.warning(f"🐛 DEBUG[{etapa}] Sem conexão DB para verificar status")
                return
            # ✅ PyMySQL: cursor() já retorna DictCursor (configurado na conexão)
            cur = conn.cursor()
            # Tenta buscar por telefone normalizado (11 dígitos)
            cur.execute("SELECT id, telefone, status FROM visitantes WHERE telefone = %s LIMIT 1", (telefone_db,))
            row = cur.fetchone()
            if row:
                log.info(f"🐛 DEBUG[{etapa}] visitante encontrado | id={row['id']} | tel={row['telefone']} | status_atual='{row['status']}'")
            else:
                # Tenta com 55+telefone
                tel_com_55 = "55" + telefone_db if not telefone_db.startswith("55") else telefone_db
                cur.execute("SELECT id, telefone, status FROM visitantes WHERE telefone = %s LIMIT 1", (tel_com_55,))
                row2 = cur.fetchone()
                if row2:
                    log.info(f"🐛 DEBUG[{etapa}] visitante encontrado (com 55) | id={row2['id']} | tel={row2['telefone']} | status_atual='{row2['status']}'")
                else:
                    log.warning(f"🐛 DEBUG[{etapa}] ❌ visitante NÃO encontrado para tel={telefone_db} ou {tel_com_55}")
    except Exception as e:
        log.error(f"🐛 DEBUG[{etapa}] Erro ao verificar status: {e}")


# =========================
# Pós-envio: campanha (confirma no CRM)
# =========================

def _pos_envio_sucesso(meta: Dict[str, Any], mensagem: str, numero_envio: str) -> None:
    """
    Pós-envio confirmado (Z-API OK):
    - salva conversa como enviada
    - atualiza status/fase quando necessário
    - trata campanha e manual
    """
    try:
        origem = meta.get("origem", "integra+")
        tipo = meta.get("tipo")  # ex.: "manual"
        telefone_raw = meta.get("telefone_raw") or _normalizar_para_salvar_no_banco(numero_envio)
        telefone_db = _normalizar_para_salvar_no_banco(telefone_raw)

        # ==========================================================
        # 1) MANUAL / BOAS-VINDAS: após envio confirmado -> INICIO
        # ==========================================================
        if tipo == "manual":
            log.info(f"🎯 Pós-envio manual | tel_db={telefone_db} | origem={origem}")
            
            # 🐛 DEBUG: Verifica status ANTES da atualização
            _debug_status_update(meta, telefone_db, origem, "ANTES_atualizar_status")
            
            # salva conversa
            try:
                salvar_conversa(
                    numero=telefone_db,
                    mensagem=mensagem,
                    tipo="enviada",
                    sid=None,
                    origem=origem
                )
                log.info(f"✅ salvar_conversa manual OK | tel={telefone_db}")
            except Exception as e:
                log.error(f"❌ salvar_conversa manual falhou: {e}")

            # ✅ Atualiza status para INICIO
            try:
                log.info(f"🔄 Chamando database.atualizar_status('{telefone_db}', 'INICIO', origem='{origem}')")
                resultado = database.atualizar_status(telefone_db, "INICIO", origem=origem)
                log.info(f"✅ atualizar_status retornou: {resultado}")
                
                # 🐛 DEBUG: Verifica status DEPOIS da atualização
                _debug_status_update(meta, telefone_db, origem, "DEPOIS_atualizar_status")
                
            except Exception as e:
                log.error(f"❌ atualizar_status(INICIO) manual falhou tel={telefone_db}: {e}", exc_info=True)

            return  # manual resolvido

        # ==========================================================
        # 2) CAMPANHA: mantém comportamento atual
        # ==========================================================
        visitante_id = meta.get("visitante_id")
        evento_nome = meta.get("evento")

        if visitante_id and evento_nome:
            try:
                salvar_conversa(
                    numero=_normalizar_para_salvar_no_banco(numero_envio),
                    mensagem=mensagem,
                    tipo="enviada",
                    sid=None,
                    origem=origem
                )
            except Exception as e:
                log.error(f"❌ salvar_conversa campanha falhou: {e}")

            try:
                database.atualizar_status_envio_evento(int(visitante_id), str(evento_nome), "enviado")
            except Exception as e:
                log.error(f"❌ atualizar_status_envio_evento(enviado) falhou: {e}")

    except Exception as e:
        log.error(f"❌ Pós-envio sucesso falhou: {e}", exc_info=True)


def _pos_envio_falha_final(meta: Dict[str, Any]) -> None:
    """Marca eventos_envios como falha quando for falha final."""
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
    global _worker_running, _anti_spam

    # 🛡️ Inicializa controller anti-spam
    _anti_spam = AntiSpamController(os.getenv("ZAPI_INSTANCE"))
    log.info(f"🛡️ AntiSpamController inicializado para instância: {_anti_spam.instance_id}")

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

            # 🛡️ VERIFICAÇÃO ANTI-SPAM ANTES DO ENVIO (com is_reply)
            pode_enviar, motivo = _check_anti_spam_and_sleep(envio_id, numero, meta)
            if not pode_enviar:
                if motivo.startswith("reequeued:"):
                    continue  # Item re-agendado, pula para próximo
                # Se foi apenas pausa, continua o loop para reavaliar
                continue

            ok = False
            last_err = ""
            last_code = 0
            last_res: Any = None

            # 📤 ENVIO DA MENSAGEM
            try:
                last_res = enviar_mensagem(numero_envio, mensagem, imagem_url)
                ok, last_err, last_code = _parse_result(last_res)
            except Exception as e:
                ok = False
                last_err = str(e)
                last_code = 0
                last_res = None

            # 🛡️ REGISTRA RESULTADO NO CONTROLLER ANTI-SPAM (com is_reply)
            if _anti_spam:
                is_reply = meta.get("is_reply", False)
                _anti_spam.register_send(ok, is_reply=is_reply)

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

            # 🛡️ DELAY ALEATÓRIO PÓS-ENVIO (anti-spam com is_reply)
            if _anti_spam:
                is_reply = meta.get("is_reply", False)
                delay = _anti_spam.get_next_delay(is_reply=is_reply)
                log.debug(f"😴 Delay aplicado: {delay:.1f}s (reply={is_reply})")
                time.sleep(delay)
            else:
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
    
    Args:
        numero: Número do destinatário (formato Z-API: 55+DDD+número)
        mensagem: Texto da mensagem
        imagem_url: URL da imagem (opcional)
        on_success: Callback para sucesso (não persiste em DB Queue)
        on_fail: Callback para falha (não persiste em DB Queue)
        meta: Metadados do envio (ex: {"tipo": "manual", "is_reply": True})
    """
    try:
        if meta is None:
            meta = {}

        numero_envio = _normalizar_para_envio(numero)
        if not numero_envio:
            log.warning("⚠️ Tentativa de enfileirar com número inválido.")
            return False

        ok = _db_insert_item(numero_envio, mensagem, imagem_url, meta)
        if not ok:
            return False

        iniciar_worker()
        return True

    except Exception as e:
        log.error(f"❌ Falha ao enfileirar (DB Queue): {e}")
        return False


# ✅ Alias para compatibilidade
enviar_mensagem_para_fila = adicionar_na_fila


# =========================
# 🛠️ Utilitários de Monitoramento
# =========================

def get_queue_anti_spam_stats() -> dict:
    """Retorna stats da fila + anti-spam para dashboard."""
    global _anti_spam
    stats = {}
    if _anti_spam:
        stats["anti_spam"] = _anti_spam.get_daily_stats()
    
    try:
        with closing(get_db_connection()) as conn:
            if conn:
                # ✅ PyMySQL: cursor() já retorna DictCursor
                cur = conn.cursor()
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN status='pendente' THEN 1 END) as pending,
                        COUNT(CASE WHEN status='processando' THEN 1 END) as processing,
                        COUNT(CASE WHEN status='enviado' THEN 1 END) as sent,
                        COUNT(CASE WHEN status='falha' THEN 1 END) as failed
                    FROM fila_envios
                    WHERE DATE(created_at) >= CURDATE()
                """)
                stats["queue_today"] = cur.fetchone() or {}
    except Exception as e:
        log.error(f"❌ Erro ao buscar stats da fila: {e}")
    
    return stats
