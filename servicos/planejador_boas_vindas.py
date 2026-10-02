import logging
import os
import threading
import time
from datetime import datetime
from contextlib import closing
from zoneinfo import ZoneInfo

from database import get_db_connection
from servicos.fila_mensagens import adicionar_na_fila

log = logging.getLogger(__name__)
_lock = threading.Lock()
_thread = None
_running = False

POLL_SECONDS = max(60, int(os.getenv("PLANEJADOR_POLL_SECONDS", "600")))
DAILY_LIMIT = max(1, int(os.getenv("FILA_DAILY_LIMIT", "20")))
BUSINESS_START = int(os.getenv("FILA_BUSINESS_HOURS_START", "8"))
BUSINESS_END = int(os.getenv("FILA_BUSINESS_HOURS_END", "20"))
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
DB_LOCK_NAME = "crm_church_planejador_boas_vindas"

WELCOME_TEMPLATE = """A Paz de Cristo, {nome}! Tudo bem com você?

Sou o *Integra+*, assistente do Ministério de Integração da MAIS DE CRISTO Canasvieiras.
Escolha uma das opções abaixo, respondendo com o número correspondente:

1⃣ Sou batizado em águas e quero me tornar membro.
2⃣ Não sou batizado e quero me tornar membro.
3⃣ Gostaria de receber orações.
4⃣ Quero saber os horários dos cultos.
5⃣ Quero entrar no grupo do WhatsApp.
6⃣ Outro assunto.

Me diga sua escolha para podermos continuar!"""


def _ensure_table(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS crm_automation_settings (
        automation_key VARCHAR(80) PRIMARY KEY, enabled TINYINT(1) NOT NULL DEFAULT 0,
        last_run DATETIME NULL, last_result VARCHAR(255) NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP)""")
    cur.execute("INSERT IGNORE INTO crm_automation_settings (automation_key,enabled) VALUES ('boas_vindas',0)")
    conn.commit(); cur.close()


def get_status():
    with closing(get_db_connection()) as conn:
        _ensure_table(conn); cur=conn.cursor()
        cur.execute("SELECT enabled,last_run,last_result,updated_at FROM crm_automation_settings WHERE automation_key='boas_vindas'")
        row=cur.fetchone() or {}
        cur.execute("SELECT COUNT(*) AS total FROM fila_envios WHERE DATE(created_at)=CURDATE() AND meta_json LIKE %s", ('%planejador_boas_vindas%',))
        scheduled=int((cur.fetchone() or {}).get("total") or 0); cur.close()
    return {"enabled":bool(row.get("enabled")),"last_run":row.get("last_run").isoformat() if row.get("last_run") else None,
            "last_result":row.get("last_result") or "Ainda não executado","updated_at":row.get("updated_at").isoformat() if row.get("updated_at") else None,
            "scheduled_today":scheduled,"daily_limit":DAILY_LIMIT,"business_hours":f"{BUSINESS_START:02d}:00–{BUSINESS_END:02d}:00",
            "poll_seconds":POLL_SECONDS}


def set_enabled(enabled: bool):
    with closing(get_db_connection()) as conn:
        _ensure_table(conn); cur=conn.cursor()
        cur.execute("UPDATE crm_automation_settings SET enabled=%s WHERE automation_key='boas_vindas'",(1 if enabled else 0,)); conn.commit(); cur.close()
    if enabled: iniciar_planejador()
    return get_status()


def _within_hours():
    hour=datetime.now(LOCAL_TZ).hour
    return BUSINESS_START <= hour < BUSINESS_END


def _remaining_capacity(conn):
    cur=conn.cursor(); cur.execute("SELECT COUNT(*) AS total FROM fila_envios WHERE DATE(created_at)=CURDATE() AND status IN ('pendente','processando','enviado')")
    used=int((cur.fetchone() or {}).get("total") or 0); cur.close(); return max(0,DAILY_LIMIT-used)


def _eligible(conn, limit):
    cur=conn.cursor(); cur.execute("""
        SELECT v.id,v.nome,v.telefone FROM visitantes v
        LEFT JOIN status s ON s.visitante_id=v.id
        WHERE (s.fase_id IS NULL OR s.fase_id='') AND v.telefone IS NOT NULL AND v.telefone<>''
          AND NOT EXISTS (
            SELECT 1 FROM fila_envios f
            WHERE RIGHT(REGEXP_REPLACE(f.numero,'[^0-9]',''),10)=RIGHT(REGEXP_REPLACE(v.telefone,'[^0-9]',''),10)
              AND f.meta_json LIKE %s AND f.status IN ('pendente','processando','enviado'))
        ORDER BY v.id ASC LIMIT %s
    """,('%boas_vindas%',limit)); rows=cur.fetchall() or []; cur.close(); return rows


def executar_uma_vez(force=False):
    with closing(get_db_connection()) as conn:
        _ensure_table(conn); cur=conn.cursor()
        cur.execute("SELECT GET_LOCK(%s,0) AS acquired",(DB_LOCK_NAME,)); acquired=int((cur.fetchone() or {}).get("acquired") or 0)
        if not acquired:
            cur.close(); return {"ok":True,"scheduled":0,"reason":"already_running"}
        try:
            cur.execute("SELECT enabled FROM crm_automation_settings WHERE automation_key='boas_vindas'")
            enabled=bool((cur.fetchone() or {}).get("enabled"))
            if not enabled and not force: return {"ok":True,"scheduled":0,"reason":"paused"}
            if not _within_hours() and not force: return {"ok":True,"scheduled":0,"reason":"outside_business_hours"}
            capacity=_remaining_capacity(conn)
            if capacity<=0: result={"ok":True,"scheduled":0,"reason":"daily_limit_reached"}
            else:
                rows=_eligible(conn,capacity); scheduled=0
                for row in rows:
                    ok=adicionar_na_fila(str(row.get("telefone") or "").strip(),WELCOME_TEMPLATE.format(nome=(row.get("nome") or "Visitante").strip()),meta={
                        "tipo":"boas_vindas","is_reply":False,"origem":"planejador_boas_vindas","visitante_id":row.get("id")})
                    if ok: scheduled+=1
                result={"ok":True,"scheduled":scheduled,"eligible":len(rows),"capacity":capacity,"reason":"scheduled"}
            summary=f"{result.get('scheduled',0)} programado(s) — {result.get('reason')}"
            cur.execute("UPDATE crm_automation_settings SET last_run=NOW(),last_result=%s WHERE automation_key='boas_vindas'",(summary,)); conn.commit()
            return result
        finally:
            try: cur.execute("SELECT RELEASE_LOCK(%s)",(DB_LOCK_NAME,))
            finally: cur.close()


def _loop():
    global _running
    while _running:
        try: executar_uma_vez()
        except Exception: log.exception("Erro no planejador automático de boas-vindas")
        time.sleep(POLL_SECONDS)


def iniciar_planejador():
    global _thread,_running
    with _lock:
        if _thread and _thread.is_alive(): return
        _running=True; _thread=threading.Thread(target=_loop,daemon=True,name="planejador-boas-vindas"); _thread.start()
        log.info("Planejador automático de boas-vindas iniciado")
