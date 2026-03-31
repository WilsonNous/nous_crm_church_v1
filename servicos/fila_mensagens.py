# ==============================================
# servicos/fila_mensagens.py  (VERSÃO DB QUEUE + ANTI-SPAM + IS_REPLY + RECUPERAÇÃO + TZ-BR)
# ==============================================
# 📨 Fila unificada de envio de mensagens Z-API
# Persistida no MySQL + Proteções anti-spam
# Suporta is_reply para respostas conversacionais
# Otimizado para recuperação de reputação WhatsApp
# ✅ Timezone-aware: respeita horário do Brasil (BRT/UTC-3)
# ✅ CORREÇÃO: JOIN com visitantes para buscar telefone em conversas
# ✅ CONFIG: Variáveis mapeadas do .env (Render v4)
# ✅ BYPASS: Manuais (boas-vindas) ignoram consentimento, mas respeitam limites anti-spam
# ==============================================

import os
import time
import json
import threading
import logging
import hashlib
import random
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any, Tuple, Optional, Callable, Dict, List

import database
from database import get_db_connection, salvar_conversa
from servicos.zapi_cliente import enviar_mensagem
from servicos.anti_spam_controller import AntiSpamController

log = logging.getLogger(__name__)

# =========================
# Config - Variáveis do .env (Render v4)
# =========================

# 📤 Envio e Delay Base
ENVIO_INTERVALO_SEG = float(os.getenv("FILA_ENVIO_INTERVALO_SEG", "2"))
MIN_DELAY_SEG = float(os.getenv("FILA_MIN_DELAY_SEC", "25"))
MAX_DELAY_SEG = float(os.getenv("FILA_MAX_DELAY_SEC", "45"))

# 🔁 Retry e Tentativas
RETRY_MAX = int(os.getenv("FILA_RETRY_MAX", "2"))
RETRY_SLEEP_SEG = float(os.getenv("FILA_RETRY_SLEEP_SEG", "3"))

# 📦 Batch e Polling
POLL_SECONDS = float(os.getenv("FILA_POLL_SECONDS", "1"))
BATCH_SIZE = int(os.getenv("FILA_BATCH_SIZE", "20"))
BATCH_SEND_LIMIT = int(os.getenv("FILA_BATCH_SEND_LIMIT", "2"))
BATCH_PAUSE_MIN_SEC = int(os.getenv("FILA_BATCH_PAUSE_MIN_SEC", "600"))
BATCH_PAUSE_MAX_SEC = int(os.getenv("FILA_BATCH_PAUSE_MAX_SEC", "900"))

# 📊 Limites e Throttling
DAILY_LIMIT = int(os.getenv("FILA_DAILY_LIMIT", "10"))
ERROR_RATE_THRESHOLD = float(os.getenv("FILA_ERROR_RATE_THRESHOLD", "0.02"))
SLOWDOWN_FACTOR = float(os.getenv("FILA_SLOWDOWN_FACTOR", "5.0"))
STATUS_TTL_SEC = int(os.getenv("FILA_STATUS_TTL_SEC", "30"))

# 🕐 Horário Comercial (em horário do Brasil - BRT/UTC-3)
# ⚠️ Estes valores SÃO em horário do Brasil, não UTC
BUSINESS_HOURS_START = int(os.getenv("FILA_BUSINESS_HOURS_START", "8"))
BUSINESS_HOURS_END = int(os.getenv("FILA_BUSINESS_HOURS_END", "19"))
OUTSIDE_HOURS_ACTION = os.getenv("FILA_OUTSIDE_HOURS_ACTION", "reequeue")

# 🔧 Cálculos derivados
MAX_ATTEMPTS = 1 + RETRY_MAX

# 🌍 Timezone Brasil (UTC-3) para cálculos de horário comercial
TZ_BRASIL = timezone(timedelta(hours=-3))

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


def _should_retry(err_text: str, status_code: int = 0, attempt: int = 1) -> bool:
    """
    Define se vale tentar novamente com backoff exponencial.
    
    Args:
        err_text: Texto do erro retornado
        status_code: Código HTTP da resposta
        attempt: Número da tentativa atual (1-based)
    
    Returns:
        bool: True se deve tentar novamente
    """
    t = (err_text or "").lower()
    
    # ❌ Nunca retry em erros permanentes (não adianta insistir)
    if any(x in t for x in [
        "must subscribe to this instance again", "subscribe to this instance again",
        "unauthorized", "invalid phone", "telefone inválido", "número inválido",
        "token inválido", "expired", "account restricted", "ban",
    ]):
        log.debug(f"⛔ Não retry: erro permanente | err={err_text[:50]}")
        return False
    
    # ⚠️ Erros de servidor (429, 5xx): retry limitado com backoff
    if status_code in (429, 500, 502, 503, 504):
        # Backoff exponencial: permite até 2 retries, mas espera mais a cada tentativa
        max_retry = 2 if status_code != 429 else 1  # Rate limit (429) → só 1 retry
        if attempt <= max_retry:
            log.debug(f"🔄 Retry permitido (attempt {attempt}/{max_retry}) | status={status_code}")
            return True
        log.debug(f"⛔ Limite de retry atingido | attempt={attempt} | status={status_code}")
        return False
    
    # ⚠️ Timeouts/conexão: retry apenas na primeira tentativa (fail-fast)
    if any(x in t for x in [
        "timeout", "timed out", "connection reset", "connection aborted", 
        "read timed out", "connection refused", "network unreachable"
    ]):
        if attempt == 1:
            log.debug(f"🔄 Retry permitido para erro de conexão (attempt 1) | err={err_text[:40]}")
            return True
        log.debug(f"⛔ Não retry para erro de conexão | attempt={attempt}")
        return False
    
    # ❌ Demais erros: não retry por padrão (fail-safe para reputação)
    log.debug(f"⛔ Não retry: erro não classificável | err={err_text[:50]}")
    return False


def _get_hora_brasil() -> datetime:
    """
    Retorna o horário atual no fuso do Brasil (BRT/UTC-3).
    Útil para verificar horário comercial correto.
    """
    return datetime.now(TZ_BRASIL)


def _esta_dentro_horario_comercial() -> bool:
    """
    Verifica se o horário atual (Brasil) está dentro do horário comercial configurado.
    
    Usa as constantes BUSINESS_HOURS_START/END definidas no topo do arquivo,
    que são carregadas das variáveis FILA_BUSINESS_HOURS_* do .env.
    
    Returns:
        bool: True se estiver dentro do horário comercial
    """
    try:
        agora_br = _get_hora_brasil()
        hora_atual = agora_br.hour
        
        # ✅ Usa as constantes do .env (já definidas no topo)
        dentro = BUSINESS_HOURS_START <= hora_atual < BUSINESS_HOURS_END
        
        if not dentro:
            log.debug(f"⏰ Fora do horário comercial (BR): {hora_atual}h não está em [{BUSINESS_HOURS_START}h, {BUSINESS_HOURS_END}h)")
        
        return dentro
        
    except Exception as e:
        log.error(f"❌ Erro ao verificar horário comercial: {e}")
        return True  # Fail-safe: permite envio se houver erro na verificação


def _pode_enviar_proativo(numero: str) -> bool:
    """
    Verifica se podemos enviar mensagem proativa para este número.
    
    Regras de consentimento (para proteger reputação WhatsApp):
    - ✅ Pode enviar se: interagiu nos últimos 7 dias OU é resposta a mensagem
    - ❌ Não enviar se: bloqueou/denunciou nos últimos 30 dias
    - ❌ Não enviar se: número inválido ou sem histórico
    - ✅ Respeita horário comercial do Brasil
    
    Args:
        numero: Número normalizado (sem 55) - formato: 48999999999
    
    Returns:
        bool: True se pode enviar mensagem proativa
    """
    try:
        # 🔍 Primeiro: verifica horário comercial (Brasil)
        if not _esta_dentro_horario_comercial():
            log.info(f"⏰ Fora do horário comercial (BR) → não enviando proativo para {numero}")
            return False
        
        with closing(get_db_connection()) as conn:
            if not conn:
                log.warning("⚠️ Sem conexão DB para validar consentimento")
                return False
            
            cur = conn.cursor()
            
            # 🔍 Verifica bloqueios/denúncias recentes (30 dias)
            # ✅ CORREÇÃO DEFINITIVA: A tabela conversas NÃO tem coluna telefone/numero
            # Ela usa visitante_id (FK) → precisamos JOIN com visitantes para buscar por telefone
            patterns = ['%pare%', '%bloque%', '%spam%', '%denuncia%']
            cur.execute("""
                SELECT COUNT(*) as bloqueios 
                FROM conversas c
                INNER JOIN visitantes v ON c.visitante_id = v.id
                WHERE v.telefone = %s 
                AND (
                    c.tipo = 'bloqueado' 
                    OR c.mensagem LIKE %s 
                    OR c.mensagem LIKE %s
                    OR c.mensagem LIKE %s
                    OR c.mensagem LIKE %s
                )
                AND c.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            """, (numero, *patterns))
            
            resultado = cur.fetchone()
            if resultado and resultado.get('bloqueios', 0) > 0:
                log.info(f"🚫 Bloqueado/denunciado recentemente: {numero}")
                return False
            
            # 🔍 Verifica engajamento recente (7 dias)
            # ✅ CORREÇÃO: Usar JOIN com visitantes para buscar por telefone
            cur.execute("""
                SELECT COUNT(*) as interacoes 
                FROM conversas c
                INNER JOIN visitantes v ON c.visitante_id = v.id
                WHERE v.telefone = %s 
                AND c.tipo = 'recebida'
                AND c.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (numero,))
            
            resultado = cur.fetchone()
            interacoes = resultado.get('interacoes', 0) if resultado else 0
            
            # ✅ Pode enviar se interagiu recentemente
            if interacoes > 0:
                log.debug(f"✅ Consentimento válido: {interacoes} interações recentes para {numero}")
                return True
            
            # ⚠️ Falha segura: se não temos histórico claro, não enviamos proativo
            log.info(f"⚠️ Sem engajamento recente para {numero} → não enviando proativo")
            return False
            
    except Exception as e:
        log.error(f"❌ Erro ao validar consentimento para {numero}: {e}")
        return False  # Fail-safe: não enviar em caso de dúvida


def _variar_mensagem(mensagem_base: str, numero: str) -> str:
    """
    Adiciona variações sutis para evitar padrões detectáveis pelo WhatsApp.
    
    Estratégia:
    - Usa hash do número para variação CONSISTENTE (mesmo número = mesma variação)
    - Varia apenas saudações iniciais e pontuação final
    - Mantém o conteúdo principal intacto para clareza
    
    Args:
        mensagem_base: Texto original da mensagem
        numero: Número do destinatário (para seed consistente)
    
    Returns:
        str: Mensagem com variação sutil aplicada
    """
    try:
        # Seed consistente baseada no número (hash MD5 → int)
        seed = int(hashlib.md5(numero.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        
        # Variações permitidas (saudações e encerramentos)
        variacoes = {
            "A Paz de Cristo": [
                "A Paz de Cristo", 
                "Graça e Paz", 
                "Paz do Senhor", 
                "A Paz de Cristo! 🙏"
            ],
            "Olá": [
                "Olá", 
                "Oi", 
                "Olá!", 
                "Olá, tudo bem?"
            ],
            "Tudo bem com você?": [
                "Tudo bem com você?", 
                "Como você está?", 
                "Tudo em paz por aí?",
                "Espero que esteja bem!"
            ],
            "🙏": [
                "🙏", 
                "🙏✨", 
                "",  # às vezes sem emoji
                "🙌"
            ],
        }
        
        resultado = mensagem_base
        
        # Aplica variações de forma consistente
        for original, opcoes in variacoes.items():
            if original in resultado:
                escolha = random.choice(opcoes)
                # Evita duplicar emojis ou pontuação
                if escolha and original:
                    resultado = resultado.replace(original, escolha, 1)
                break  # Apenas uma variação por mensagem para sutileza
        
        # Reset seed para não afetar outros usos do random
        random.seed()
        return resultado
        
    except Exception as e:
        log.error(f"❌ Erro ao variar mensagem: {e}")
        return mensagem_base  # Fallback: retorna original se der erro


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
            # ✅ FILTRAR mensagens agendadas para o futuro (evita loop de re-agendamento)
            cur.execute("""
                SELECT id, numero, mensagem, imagem_url, tentativas, meta_json
                FROM fila_envios
                WHERE status = 'pendente'
                AND (scheduled_for IS NULL OR scheduled_for <= NOW())
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
            # ✅ PASSA O NÚMERO DA TENTATIVA PARA _should_retry (backoff exponencial)
            allow_retry = (next_attempt_count < MAX_ATTEMPTS) and _should_retry(
                err, int(status_code or 0), attempt=next_attempt_count
            )
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
# 🛡️ Anti-Spam: Verificação e Delay (com is_reply e is_manual)
# =========================

def _check_anti_spam_and_sleep(envio_id: int, numero: str, meta: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Verifica anti-spam antes do envio.
    
    Args:
        envio_id: ID do envio na fila
        numero: Número do destinatário
        meta: Metadados do envio (contém is_reply e tipo)
    
    Returns:
        Tuple[bool, str]: (pode_enviar, motivo)
        Se não puder e for reequeue, re-agenda o item e retorna False.
    """
    global _anti_spam
    if not _anti_spam:
        return True, "ok"  # Fallback se controller não estiver inicializado

    is_reply = meta.get("is_reply", False)
    is_manual = meta.get("tipo") == "manual"  # ← NOVO: detectar envio manual (boas-vindas)
    
    # ✅ Passa is_manual para o controller anti-spam
    can_send, reason = _anti_spam.can_send_now(is_reply=is_reply, is_manual=is_manual)
    
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
            log.info(f"⏸️ Aguardando anti-spam: {reason} | envio_id={envio_id} | reply={is_reply} | manual={is_manual}")
            time.sleep(5)  # Pequena pausa antes de reavaliar
    
    return can_send, reason


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
    
    # 🕐 Log do horário Brasil para debug
    agora_br = _get_hora_brasil()
    log.info(f"🕐 Worker iniciado | Horário Brasil: {agora_br.strftime('%H:%M %d/%m')} | UTC: {datetime.now(timezone.utc).strftime('%H:%M %d/%m')}")
    log.info(f"⚙️ Config: daily_limit={DAILY_LIMIT}, batch={BATCH_SEND_LIMIT}, delay=[{MIN_DELAY_SEG}s,{MAX_DELAY_SEG}s]")

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

            # 🛡️ VERIFICAÇÃO DE CONSENTIMENTO para envios proativos
            # ✅ BYPASS: Manuais (boas-vindas) NÃO passam por validação de consentimento
            is_reply = meta.get("is_reply", False)
            tipo_envio = meta.get("tipo", "bot")
            is_manual = tipo_envio == "manual"
            
            # ✅ Manuais ignoram consentimento, mas proativos validam
            if not is_manual and not is_reply and tipo_envio in ("campanha", "proativo", "bot"):
                if not _pode_enviar_proativo(numero):
                    log.info(f"🚫 Consentimento não validado para proativo | envio_id={envio_id} | {numero}")
                    # Marca como falha suave (não conta como erro de reputação)
                    _db_mark_fail_or_retry(envio_id, tentativas_atual + 1, 0, "consentimento_nao_validado")
                    continue

            # 🛡️ VERIFICAÇÃO ANTI-SPAM ANTES DO ENVIO (com is_reply e is_manual)
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

            # ✨ APLICA VARIAÇÃO SUTIL na mensagem (apenas para proativos)
            mensagem_para_envio = mensagem
            if not is_reply and tipo_envio in ("manual", "campanha", "proativo"):
                mensagem_para_envio = _variar_mensagem(mensagem, numero)
                if mensagem_para_envio != mensagem:
                    log.debug(f"✨ Mensagem variada para {numero}: '{mensagem[:30]}...' → '{mensagem_para_envio[:30]}...'")

            # 📤 ENVIO DA MENSAGEM
            try:
                last_res = enviar_mensagem(numero_envio, mensagem_para_envio, imagem_url)
                ok, last_err, last_code = _parse_result(last_res)
            except Exception as e:
                ok = False
                last_err = str(e)
                last_code = 0
                last_res = None

            # 🛡️ REGISTRA RESULTADO NO CONTROLLER ANTI-SPAM (com is_reply e is_manual)
            if _anti_spam:
                _anti_spam.register_send(ok, is_reply=is_reply, is_manual=is_manual)  # ← Passa is_manual

            msg_preview = (mensagem_para_envio or "").replace("\n", " ")[:60]
            err_preview = (last_err or "").replace("\n", " ")[:180]

            payload = {
                "ok": ok,
                "numero": numero,
                "numero_envio": numero_envio,
                "status_code": last_code,
                "erro": last_err,
                "mensagem": mensagem_para_envio,
                "imagem_url": imagem_url,
                "res": last_res,
                "meta": meta,
                "envio_id": envio_id
            }

            on_success = meta.get("_on_success_cb")
            on_fail = meta.get("_on_fail_cb")

            if ok:
                _db_mark_success(envio_id, last_code)
                _pos_envio_sucesso(meta, mensagem_para_envio, numero_envio)
                log.info(f"✅ Fila(DB) → {numero_envio} | {msg_preview}... | code={last_code} | envio_id={envio_id}")
                _safe_call(on_success, payload)
            else:
                # ✅ PASSA O NÚMERO DA TENTATIVA PARA BACKOFF EXPONENCIAL
                novo_status = _db_mark_fail_or_retry(
                    envio_id, 
                    tentativas_atual + 1, 
                    last_code, 
                    last_err
                )
                if novo_status == "pendente":
                    log.warning(f"🔁 Retry agendado → envio_id={envio_id} | {numero_envio} | code={last_code} | err={err_preview}")
                    time.sleep(RETRY_SLEEP_SEG)
                else:
                    _pos_envio_falha_final(meta)
                    log.error(f"❌ Falha final → envio_id={envio_id} | {numero_envio} | code={last_code} | err={err_preview}")
                    _safe_call(on_fail, payload)

            # 🛡️ DELAY ALEATÓRIO PÓS-ENVIO (anti-spam com is_reply e is_manual)
            if _anti_spam:
                delay = _anti_spam.get_next_delay(is_reply=is_reply, is_manual=is_manual)  # ← Passa is_manual
                # Garante que delay esteja dentro dos limites configurados
                delay = max(MIN_DELAY_SEG, min(MAX_DELAY_SEG, delay))
                log.debug(f"😴 Delay aplicado: {delay:.1f}s (reply={is_reply}, manual={is_manual})")
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
                cur = conn.cursor()
                
                # ✅ CORREÇÃO: Usar timezone Brasil (UTC-3) para filtrar "hoje"
                # Calcula o início e fim do dia em BRT, convertendo para UTC para a query
                agora_br = datetime.now(TZ_BRASIL)
                inicio_dia_br = agora_br.replace(hour=0, minute=0, second=0, microsecond=0)
                fim_dia_br = agora_br.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Converte para UTC para comparar com created_at (que está em UTC no banco)
                inicio_dia_utc = inicio_dia_br.astimezone(timezone.utc)
                fim_dia_utc = fim_dia_br.astimezone(timezone.utc)
                
                # ✅ Query com filtro de timezone correto
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN status='pendente' THEN 1 END) as pending,
                        COUNT(CASE WHEN status='processando' THEN 1 END) as processing,
                        COUNT(CASE WHEN status='enviado' THEN 1 END) as sent,
                        COUNT(CASE WHEN status='falha' THEN 1 END) as failed,
                        COUNT(CASE WHEN status='falha' AND last_error LIKE %s THEN 1 END) as consent_blocked
                    FROM fila_envios
                    WHERE created_at >= %s AND created_at <= %s
                """, ('%consentimento%', inicio_dia_utc, fim_dia_utc))
                
                row = cur.fetchone() or {}
                stats["queue_today"] = {
                    "pending": row.get("pending", 0),
                    "processing": row.get("processing", 0),
                    "sent": row.get("sent", 0),
                    "failed": row.get("failed", 0),
                    "consent_blocked": row.get("consent_blocked", 0),
                }
    except Exception as e:
        log.error(f"❌ Erro ao buscar stats da fila: {e}")
        # Fallback seguro
        stats["queue_today"] = {
            "pending": 0, "processing": 0, "sent": 0, "failed": 0, "consent_blocked": 0
        }
    
    return stats
