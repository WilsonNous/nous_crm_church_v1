import logging
from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, timedelta
from contextlib import closing
from database import get_db_connection
from servicos.fila_mensagens import get_queue_anti_spam_stats

monitor_bp = Blueprint("app_monitor_bp", __name__)

def register(app):
    app.register_blueprint(monitor_bp)


# ===========================
# Página principal do monitor
# ===========================
@monitor_bp.route('/app/monitor')
def monitor_page():
    return render_template('app_monitor.html')


# ===========================
# API — Listar Visitantes
# ===========================
@monitor_bp.route('/api/monitor/visitantes', methods=['GET'])
def monitor_visitantes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()   # DictCursor já é aplicado automaticamente

        cursor.execute("""
            SELECT id, nome, telefone
            FROM visitantes
            ORDER BY nome ASC
        """)

        visitantes = cursor.fetchall()  # já devolve dicionários ❤️

        cursor.close()
        conn.close()
        return jsonify({"status": "success", "visitantes": visitantes})

    except Exception as e:
        logging.error(f"Erro em /api/monitor/visitantes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ===========================
# API — Listar Conversas
# ===========================
@monitor_bp.route('/api/monitor/conversas/<int:visitante_id>', methods=['GET'])
def monitor_conversas_visitante(visitante_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()  # DictCursor

        cursor.execute("""
            SELECT 
                c.id,
                c.mensagem,
                c.tipo,
                c.data_hora,
                v.nome AS visitante_nome,
                CASE 
                    WHEN LOWER(c.tipo) = 'enviada' THEN 'Integra+'
                    WHEN LOWER(c.tipo) = 'recebida' THEN v.nome
                    ELSE 'Desconhecido'
                END AS autor
            FROM conversas c
            JOIN visitantes v ON v.id = c.visitante_id
            WHERE v.id = %s
            ORDER BY c.data_hora ASC
        """, (visitante_id,))

        conversas = cursor.fetchall()  # já vem como dict ❤️

        cursor.close()
        conn.close()

        return jsonify({"status": "success", "conversas": conversas}), 200

    except Exception as e:
        logging.error(f"Erro em /api/monitor/conversas/{visitante_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================================
# 🆕 NOVAS ROTAS: Métricas WhatsApp para Dashboard
# ==========================================================

@monitor_bp.route('/api/monitor-status', methods=['GET'])
def monitor_status():
    """
    Retorna métricas consolidadas da fila WhatsApp + anti-spam para o dashboard.
    Usado pelo painel /app/whatsapp para visualização em tempo real.
    """
    try:
        # Stats da fila + anti-spam (já implementado em fila_mensagens.py)
        stats = get_queue_anti_spam_stats()
        
        # Busca últimos envios para a tabela "Últimos Envios"
        recent_sends = _get_recent_sends(limit=10)
        
        # Calcula métricas derivadas
        queue = stats.get("queue_today", {})
        sent = queue.get("sent", 0)
        failed = queue.get("failed", 0)
        attempted = sent + failed
        
        delivery_rate = round((sent / max(attempted, 1)) * 100)
        
        # Determina status de saúde
        if delivery_rate >= 95:
            health_status = "healthy"
            health_message = "🟢 Saudável"
        elif delivery_rate >= 80:
            health_status = "warning"
            health_message = "🟡 Atenção"
        else:
            health_status = "critical"
            health_message = "🔴 Crítico"
        
        return jsonify({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            
            # Métricas da fila
            "queue_today": {
                "pending": queue.get("pending", 0),
                "processing": queue.get("processing", 0),
                "sent": queue.get("sent", 0),
                "failed": queue.get("failed", 0),
                "consent_blocked": queue.get("consent_blocked", 0),
                "total": queue.get("pending", 0) + queue.get("processing", 0) + 
                        queue.get("sent", 0) + queue.get("failed", 0) + queue.get("consent_blocked", 0)
            },
            
            # Métricas do anti-spam
            "anti_spam": stats.get("anti_spam", {
                "daily_limit": 20,
                "sent": 0,
                "can_send_now": True,
                "next_delay_sec": 15
            }),
            
            # Métricas calculadas
            "delivery_rate": delivery_rate,
            "health_status": health_status,
            "health_message": health_message,
            
            # Últimos envios para a tabela
            "recent_sends": recent_sends
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Erro em /api/monitor-status: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e),
            "queue_today": {},
            "anti_spam": {},
            "recent_sends": []
        }), 500


@monitor_bp.route('/api/fila/recentes', methods=['GET'])
def fila_recentes():
    """
    Retorna os últimos registros da fila_envios para exibição na tabela.
    Parâmetros opcionais:
    - limit: número de registros (default: 20)
    - status: filtrar por status (pendente|processando|enviado|falha)
    - date: filtrar por data (YYYY-MM-DD)
    """
    try:
        limit = request.args.get('limit', default=20, type=int)
        status_filter = request.args.get('status', default=None)
        date_filter = request.args.get('date', default=None)
        
        recent_sends = _get_recent_sends(
            limit=min(limit, 100),  # Segurança: máximo 100
            status=status_filter,
            date=date_filter
        )
        
        return jsonify({
            "status": "success",
            "total": len(recent_sends),
            "data": recent_sends
        }), 200
        
    except Exception as e:
        logging.error(f"❌ Erro em /api/fila/recentes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@monitor_bp.route('/api/fila/consent-stats', methods=['GET'])
def fila_consent_stats():
    """
    Retorna estatísticas específicas sobre bloqueios por consentimento.
    Útil para monitorar a eficácia da validação de consentimento.
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return jsonify({"error": "Sem conexão"}), 500
            
            cursor = conn.cursor()
            
            # Bloqueios por consentimento nos últimos 7 dias
            cursor.execute("""
                SELECT 
                    DATE(created_at) as dia,
                    COUNT(*) as bloqueados,
                    SUM(CASE WHEN status='pendente' THEN 1 ELSE 0 END) as re_agendados
                FROM fila_envios
                WHERE last_error LIKE '%consentimento%'
                AND created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY DATE(created_at)
                ORDER BY dia DESC
            """)
            history = cursor.fetchall() or []
            
            # Top números com mais bloqueios
            cursor.execute("""
                SELECT 
                    numero,
                    COUNT(*) as total_bloqueios,
                    MAX(created_at) as ultimo_bloqueio
                FROM fila_envios
                WHERE last_error LIKE '%consentimento%'
                AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY numero
                ORDER BY total_bloqueios DESC
                LIMIT 10
            """)
            top_blocked = cursor.fetchall() or []
            
            return jsonify({
                "status": "success",
                "period": "7_days",
                "history": [
                    {
                        "date": row["dia"].isoformat() if row["dia"] else None,
                        "blocked": row["bloqueados"],
                        "rescheduled": row["re_agendados"]
                    }
                    for row in history
                ],
                "top_blocked_numbers": [
                    {
                        "numero": row["numero"],
                        "total_blocks": row["total_bloqueios"],
                        "last_block": row["ultimo_bloqueio"].isoformat() if row["ultimo_bloqueio"] else None
                    }
                    for row in top_blocked
                ]
            }), 200
            
    except Exception as e:
        logging.error(f"❌ Erro em /api/fila/consent-stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================================
# 🔧 Funções Auxiliares Internas
# ==========================================================

def _get_recent_sends(limit: int = 10, status: str = None, date: str = None) -> list:
    """
    Busca últimos envios da fila_envios com filtros opcionais.
    Função interna para reuso entre endpoints.
    """
    try:
        with closing(get_db_connection()) as conn:
            if not conn:
                return []
            
            cursor = conn.cursor()
            
            # Constrói query com filtros opcionais
            query = """
                SELECT 
                    id, numero, mensagem, status, created_at, last_error,
                    JSON_EXTRACT(meta_json, '$.is_reply') as is_reply,
                    JSON_EXTRACT(meta_json, '$.tipo') as tipo_envio
                FROM fila_envios
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            if date:
                query += " AND DATE(created_at) = %s"
                params.append(date)
            
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() or []
            
            # Formata para frontend
            result = []
            for row in rows:
                # Formata número para exibição
                numero = row["numero"] or ""
                if len(numero) == 13 and numero.startswith("55"):
                    # Formato: 5548999999999 → (48) 99999-9999
                    ddd = numero[2:4]
                    parte1 = numero[4:9]
                    parte2 = numero[9:13]
                    numero_formatado = f"({ddd}) {parte1}-{parte2}"
                else:
                    numero_formatado = numero
                
                # Preview da mensagem
                mensagem = row["mensagem"] or ""
                msg_preview = mensagem[:50] + ("..." if len(mensagem) > 50 else "")
                
                # Status legível
                status_label = {
                    "pendente": "⏳ Pendente",
                    "processando": "🔄 Processando", 
                    "enviado": "✅ Entregue",
                    "falha": "❌ Falha"
                }.get(row["status"], row["status"])
                
                result.append({
                    "id": row["id"],
                    "numero": numero_formatado,
                    "numero_raw": row["numero"],
                    "mensagem": msg_preview,
                    "mensagem_completa": mensagem,
                    "status": row["status"],
                    "status_label": status_label,
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "last_error": row["last_error"][:100] if row["last_error"] else None,
                    "is_reply": bool(row["is_reply"]) if row["is_reply"] is not None else False,
                    "tipo_envio": row["tipo_envio"] or "bot"
                })
            
            return result
            
    except Exception as e:
        logging.error(f"❌ Erro em _get_recent_sends: {e}")
        return []
