# ==============================================
# servicos/anti_spam_controller.py
# ==============================================
# 🛡️ Controlador de rate limiting anti-spam para Z-API/WhatsApp
# Previne bloqueios por envio em massa com comportamento humano
# Instância: 3E6F0EC5A375B0F52279DEB451C64861
# ==============================================

import os
import time
import random
import logging
from datetime import datetime, timedelta
from contextlib import closing
from typing import Tuple, Dict, Optional

from database import get_db_connection

log = logging.getLogger(__name__)

# ==============================================
# Configurações via Environment Variables
# ==============================================
MIN_DELAY_SEC = float(os.getenv("FILA_MIN_DELAY_SEC", "3"))
MAX_DELAY_SEC = float(os.getenv("FILA_MAX_DELAY_SEC", "8"))
BATCH_SEND_LIMIT = int(os.getenv("FILA_BATCH_SEND_LIMIT", "10"))
BATCH_PAUSE_MIN_SEC = float(os.getenv("FILA_BATCH_PAUSE_MIN_SEC", "60"))
BATCH_PAUSE_MAX_SEC = float(os.getenv("FILA_BATCH_PAUSE_MAX_SEC", "180"))
DAILY_LIMIT = int(os.getenv("FILA_DAILY_LIMIT", "300"))  # 0 = ilimitado
BUSINESS_START = int(os.getenv("FILA_BUSINESS_HOURS_START", "8"))
BUSINESS_END = int(os.getenv("FILA_BUSINESS_HOURS_END", "20"))
OUTSIDE_HOURS_ACTION = os.getenv("FILA_OUTSIDE_HOURS_ACTION", "reequeue").lower()
ERROR_RATE_THRESHOLD = float(os.getenv("FILA_ERROR_RATE_THRESHOLD", "0.15"))
SLOWDOWN_FACTOR = float(os.getenv("FILA_SLOWDOWN_FACTOR", "2.0"))


class AntiSpamController:
    """
    Controla rate limiting para evitar bloqueios do WhatsApp/Z-API.
    
    Camadas de proteção:
    1. Delay aleatório entre mensagens (jitter) → evita padrão robótico
    2. Batches com pausas obrigatórias → simula comportamento humano
    3. Limite diário por instância → previne volume suspeito
    4. Janela de horário comercial → evita envios noturnos
    5. Throttling adaptativo → reduz velocidade se erros aumentarem
    
    Thread-safe para uso em worker único (Gunicorn com gthread).
    """
    
    def __init__(self, instance_id: Optional[str] = None):
        """
        Inicializa o controller.
        
        Args:
            instance_id: ID da instância Z-API. Se None, usa env var.
        """
        self.instance_id = instance_id or os.getenv("ZAPI_INSTANCE") or "default"
        self._cache: Dict = {}
        self._cache_ts: float = 0
        self._cache_ttl: int = 30  # segundos

    # ------------------------------------------
    # Helpers Internos
    # ------------------------------------------
    def _get_today_key(self) -> str:
        """Retorna chave de data no formato YYYY-MM-DD."""
        return datetime.now().date().isoformat()

    def _fetch_limits(self) -> dict:
        """
        Busca dados de rate limit do banco (com cache em memória).
        ✅ Corrigido: usa cursor() sem argumentos (PyMySQL já retorna dict)
        """
        now = time.time()
        
        # Retorna do cache se válido (evita queries excessivas)
        if now - self._cache_ts < self._cache_ttl:
            return self._cache.copy()

        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    log.warning("⚠️ Sem conexão com DB para rate limits")
                    return self._default_limits()
                    
                # ✅ PyMySQL: cursor() já retorna DictCursor (configurado na conexão)
                cur = conn.cursor()
                today = self._get_today_key()
                
                # Garante que existe registro para hoje (upsert)
                cur.execute("""
                    INSERT INTO fila_rate_limit (instance_id, date)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE updated_at=NOW()
                """, (self.instance_id, today))
                conn.commit()
                
                # Busca os dados atuais
                cur.execute("""
                    SELECT total_sent, total_failed, messages_in_current_batch,
                           last_batch_pause_at, current_error_rate, slowdown_active
                    FROM fila_rate_limit
                    WHERE instance_id=%s AND date=%s
                """, (self.instance_id, today))
                
                row = cur.fetchone() or {}
                
                self._cache = {
                    "total_sent": int(row.get("total_sent") or 0),
                    "total_failed": int(row.get("total_failed") or 0),
                    "messages_in_batch": int(row.get("messages_in_current_batch") or 0),
                    "last_batch_pause": row.get("last_batch_pause_at"),
                    "error_rate": float(row.get("current_error_rate") or 0),
                    "slowdown_active": bool(row.get("slowdown_active") or False),
                }
                self._cache_ts = now
                return self._cache.copy()
                
        except Exception as e:
            log.error(f"❌ Erro ao buscar rate limits: {e}")
            return self._default_limits()

    def _default_limits(self) -> dict:
        """Retorna valores padrão em caso de erro no banco."""
        return {
            "total_sent": 0,
            "total_failed": 0,
            "messages_in_batch": 0,
            "error_rate": 0.0,
            "slowdown_active": False
        }

    def _update_counter(self, field: str, increment: int = 1):
        """
        Atualiza contador no banco de forma atômica.
        
        Args:
            field: Nome do campo a atualizar
            increment: Valor a somar (padrão: 1)
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return
                cur = conn.cursor()
                today = self._get_today_key()
                cur.execute(f"""
                    UPDATE fila_rate_limit
                    SET {field} = {field} + %s, updated_at = NOW()
                    WHERE instance_id=%s AND date=%s
                """, (increment, self.instance_id, today))
                conn.commit()
                # Invalida cache para próxima leitura
                self._cache_ts = 0
        except Exception as e:
            log.error(f"❌ Erro ao atualizar contador '{field}': {e}")

    def _update_error_rate(self, was_success: bool):
        """
        Recalcula taxa de erro com média móvel simples.
        
        Args:
            was_success: True se o envio foi bem-sucedido
        """
        try:
            limits = self._fetch_limits()
            total = limits["total_sent"] + limits["total_failed"] + 1
            failed = limits["total_failed"] + (0 if was_success else 1)
            new_rate = failed / max(total, 1)
            
            with closing(get_db_connection()) as conn:
                if not conn:
                    return
                cur = conn.cursor()
                today = self._get_today_key()
                slowdown = new_rate > ERROR_RATE_THRESHOLD
                
                cur.execute("""
                    UPDATE fila_rate_limit
                    SET current_error_rate=%s, slowdown_active=%s, updated_at=NOW()
                    WHERE instance_id=%s AND date=%s
                """, (round(new_rate, 3), slowdown, self.instance_id, today))
                conn.commit()
                self._cache_ts = 0
                
        except Exception as e:
            log.error(f"❌ Erro ao atualizar error_rate: {e}")

    def _get_batch_pause_duration(self, slowdown: bool) -> float:
        """
        Calcula duração da pausa entre batches.
        
        Args:
            slowdown: Se deve aplicar fator de redução de velocidade
            
        Returns:
            float: segundos de pausa necessários
        """
        base_pause = random.uniform(BATCH_PAUSE_MIN_SEC, BATCH_PAUSE_MAX_SEC)
        return base_pause * (SLOWDOWN_FACTOR if slowdown else 1.0)

    def _register_batch_pause(self):
        """Registra que um batch foi concluído e pausa iniciada."""
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return
                cur = conn.cursor()
                today = self._get_today_key()
                cur.execute("""
                    UPDATE fila_rate_limit
                    SET messages_in_current_batch=0,
                        last_batch_pause_at=NOW(),
                        updated_at=NOW()
                    WHERE instance_id=%s AND date=%s
                """, (self.instance_id, today))
                conn.commit()
                self._cache_ts = 0
        except Exception as e:
            log.error(f"❌ Erro ao registrar batch pause: {e}")

    # ------------------------------------------
    # API Pública - Verificações
    # ------------------------------------------
    def can_send_now(self) -> Tuple[bool, str]:
        """
        Verifica se pode enviar mensagem agora.
        
        Returns:
            Tuple[bool, str]: 
                - (True, "ok") se pode enviar
                - (False, motivo) se não pode
                - Se motivo começar com "reequeue:", o restante é ISO datetime
        """
        limits = self._fetch_limits()
        now = datetime.now()
        current_hour = now.hour

        # 1. Verifica limite diário
        if DAILY_LIMIT > 0 and limits["total_sent"] >= DAILY_LIMIT:
            log.warning(f"🚫 Limite diário atingido: {limits['total_sent']}/{DAILY_LIMIT}")
            return False, f"Limite diário atingido ({DAILY_LIMIT} envios)"

        # 2. Verifica janela de horário comercial
        if not (BUSINESS_START <= current_hour < BUSINESS_END):
            if OUTSIDE_HOURS_ACTION == "skip":
                log.info(f"⏭️ Fora do horário comercial ({BUSINESS_START}h-{BUSINESS_END}h) - pulando")
                return False, f"Fora do horário comercial ({BUSINESS_START}h-{BUSINESS_END}h)"
            elif OUTSIDE_HOURS_ACTION == "reequeue":
                # Calcula próximo horário permitido
                if current_hour < BUSINESS_START:
                    next_send = now.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0)
                else:
                    # Já passou do horário: agenda para amanhã
                    next_send = now.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0) + timedelta(days=1)
                log.info(f"⏰ Fora do horário - re-agendando para {next_send}")
                return False, f"reequeue:{next_send.isoformat()}"

        # 3. Verifica se precisa de pausa entre batches
        if limits["messages_in_batch"] >= BATCH_SEND_LIMIT:
            if limits["last_batch_pause"]:
                last_pause = limits["last_batch_pause"]
                # Converte para datetime se for string (MySQL retorna assim)
                if isinstance(last_pause, str):
                    # Tenta parsear ISO format, remove timezone info se houver
                    last_pause_str = last_pause.replace("Z", "+00:00")
                    if "+" in last_pause_str and last_pause_str.count("+") == 1:
                        last_pause_str = last_pause_str.split("+")[0]
                    try:
                        last_pause = datetime.fromisoformat(last_pause_str)
                    except ValueError:
                        # Fallback para formato MySQL padrão
                        last_pause = datetime.strptime(last_pause_str[:19], "%Y-%m-%d %H:%M:%S")
                
                elapsed = (now - last_pause).total_seconds()
                pause_needed = self._get_batch_pause_duration(limits["slowdown_active"])
                
                if elapsed < pause_needed:
                    remaining = int(pause_needed - elapsed)
                    log.info(f"⏸️ Pausa entre batches: aguarde {remaining}s")
                    return False, f"Pausa entre batches: aguarde {remaining}s"
            
            # Batch completo: registra pausa e reseta contador
            log.info(f"📦 Batch de {BATCH_SEND_LIMIT} mensagens concluído - iniciando pausa")
            self._register_batch_pause()

        # 4. Log se throttling adaptativo estiver ativo
        if limits["slowdown_active"]:
            log.warning(
                f"🐌 Throttling adaptativo ATIVO | "
                f"error_rate={limits['error_rate']:.1%} > {ERROR_RATE_THRESHOLD:.1%} | "
                f"delays multiplicados por {SLOWDOWN_FACTOR}x"
            )

        return True, "ok"

    # ------------------------------------------
    # API Pública - Registro de Envios
    # ------------------------------------------
    def register_send(self, success: bool):
        """
        Registra um envio concluído e atualiza métricas.
        
        Args:
            success: True se o envio foi bem-sucedido, False caso contrário
        """
        # Atualiza contador de enviados/falhas
        self._update_counter("total_sent" if success else "total_failed")
        
        # Só incrementa batch se foi sucesso (falha não conta como "envio válido")
        if success:
            self._update_counter("messages_in_current_batch")
        
        # Recalcula taxa de erro
        self._update_error_rate(success)
        
        # Log resumido para monitoramento
        limits = self._fetch_limits()
        log.debug(
            f"📊 Rate limit update | sent={limits['total_sent']}/{DAILY_LIMIT if DAILY_LIMIT>0 else '∞'} | "
            f"batch={limits['messages_in_batch']}/{BATCH_SEND_LIMIT} | "
            f"error_rate={limits['error_rate']:.1%} | "
            f"slowdown={limits['slowdown_active']}"
        )

    def get_next_delay(self) -> float:
        """
        Calcula delay até o próximo envio (com jitter e slowdown).
        
        Returns:
            float: segundos para aguardar antes do próximo envio
        """
        limits = self._fetch_limits()
        base_min = MIN_DELAY_SEC
        base_max = MAX_DELAY_SEC
        
        # Aplica slowdown se taxa de erro estiver alta
        if limits["slowdown_active"]:
            base_min *= SLOWDOWN_FACTOR
            base_max *= SLOWDOWN_FACTOR
        
        # Jitter aleatório para evitar padrão detectável
        delay = random.uniform(base_min, base_max)
        log.debug(f"⏱️ Delay calculado: {delay:.1f}s (slowdown={limits['slowdown_active']})")
        return delay

    # ------------------------------------------
    # API Pública - Monitoramento e Utilitários
    # ------------------------------------------
    def get_daily_stats(self) -> dict:
        """
        Retorna estatísticas do dia para monitoramento.
        
        Returns:
            dict com métricas atuais do rate limiting
        """
        limits = self._fetch_limits()
        can_send, reason = self.can_send_now()
        
        return {
            "instance_id": self.instance_id,
            "date": self._get_today_key(),
            "sent": limits["total_sent"],
            "failed": limits["total_failed"],
            "daily_limit": DAILY_LIMIT if DAILY_LIMIT > 0 else "ilimitado",
            "remaining": max(0, DAILY_LIMIT - limits["total_sent"]) if DAILY_LIMIT > 0 else "∞",
            "in_batch": limits["messages_in_batch"],
            "batch_limit": BATCH_SEND_LIMIT,
            "error_rate": round(limits["error_rate"] * 100, 1),
            "slowdown_active": limits["slowdown_active"],
            "can_send_now": can_send,
            "block_reason": None if can_send else reason,
            "next_delay_sec": round(self.get_next_delay(), 1),
            "config": {
                "min_delay": MIN_DELAY_SEC,
                "max_delay": MAX_DELAY_SEC,
                "batch_limit": BATCH_SEND_LIMIT,
                "batch_pause_range": f"{BATCH_PAUSE_MIN_SEC}-{BATCH_PAUSE_MAX_SEC}s",
                "business_hours": f"{BUSINESS_START}h-{BUSINESS_END}h",
                "outside_hours_action": OUTSIDE_HOURS_ACTION,
            }
        }

    def reset_batch_counter(self):
        """Força reset do contador de batch (útil para testes ou recuperação)."""
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return
                cur = conn.cursor()
                today = self._get_today_key()
                cur.execute("""
                    UPDATE fila_rate_limit
                    SET messages_in_current_batch=0, updated_at=NOW()
                    WHERE instance_id=%s AND date=%s
                """, (self.instance_id, today))
                conn.commit()
                self._cache_ts = 0
                log.info(f"🔄 Batch counter resetado para {self.instance_id}")
        except Exception as e:
            log.error(f"❌ Erro ao resetar batch counter: {e}")

    def reset_daily_limits(self):
        """
        Reseta todos os limites do dia (útil para cron job à meia-noite).
        Pode ser chamado manualmente se necessário.
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return
                cur = conn.cursor()
                today = self._get_today_key()
                cur.execute("""
                    INSERT INTO fila_rate_limit (instance_id, date)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE 
                        total_sent = 0,
                        total_failed = 0,
                        messages_in_current_batch = 0,
                        slowdown_active = FALSE,
                        current_error_rate = 0.000,
                        updated_at = NOW()
                """, (self.instance_id, today))
                conn.commit()
                self._cache_ts = 0
                log.info(f"🔄 Limites diários resetados para {self.instance_id}")
        except Exception as e:
            log.error(f"❌ Erro ao resetar limites diários: {e}")

    def force_allow_send(self, reason: str = "override_admin") -> bool:
        """
        Força permissão de envio (bypass das verificações).
        Use com extrema cautela - apenas para situações emergenciais.
        
        Args:
            reason: Motivo do bypass (para logging)
            
        Returns:
            bool: True se bypass aplicado
        """
        log.warning(f"⚠️ BYPASS ANTI-SPAM ativado | motivo: {reason} | instance: {self.instance_id}")
        return True
