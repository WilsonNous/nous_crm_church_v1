import logging
from flask import request, jsonify, render_template, session, redirect, url_for
from database import get_db_connection
from servicos.anti_spam_controller import AntiSpamController
import os

def register(app):
    # ============================================================
    # 🧠 Painel Admin de Aprendizado Manual
    # ============================================================
    @app.route('/admin/integra/learn')
    def integra_learn_dashboard():
        if not session.get('integra_admin_logged_in'):
            return redirect(url_for('login_page'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, question, created_at
            FROM unknown_questions
            WHERE status='pending'
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        questions = [{"id": r[0], "user_id": r[1], "question": r[2], "created_at": r[3]} for r in rows]
        cursor.close()
        conn.close()
        return render_template('admin_integra_learn.html', questions=questions)

    # ============================================================
    # 🔎 Perguntas Pendentes (usado pelo painel /app/ia)
    # ============================================================
    @app.route('/api/ia/pending-questions', methods=['GET'])
    def ia_pending_questions():
        try:
            logging.info("🧩 Iniciando /api/ia/pending-questions")
            conn = get_db_connection()
            if not conn:
                raise Exception("get_db_connection() retornou None")

            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, question, created_at
                FROM unknown_questions
                WHERE status='pending'
            """)
            rows = cursor.fetchall()
            perguntas = [
                {
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "question": r["question"],
                    "created_at": r["created_at"]
                } for r in rows
            ]

            cursor.close()
            conn.close()
            logging.info(f"✅ Total perguntas pendentes: {len(perguntas)}")
            return jsonify({"questions": perguntas}), 200

        except Exception as e:
            logging.exception("❌ Erro em /api/ia/pending-questions:")
            return jsonify({"error": str(e)}), 500

    # ============================================================
    # 💬 Treinamento da IA (ensinar pergunta e resposta)
    # ============================================================
    @app.route('/api/ia/teach', methods=['POST'])
    def ia_teach():
        conn = None
        cursor = None
        try:
            data = request.get_json(force=True) or {}
            question = (data.get('question') or '').strip()
            answer = (data.get('answer') or '').strip()
            category = (data.get('category') or '').strip()

            # 🔒 Validação
            if not question or not answer or not category:
                return jsonify({"error": "Campos obrigatórios ausentes."}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # 🔍 Verifica se já existe a pergunta
            cursor.execute("SELECT id FROM knowledge_base WHERE question = %s", (question,))
            existing = cursor.fetchone()

            if existing:
                # Atualiza resposta existente (Upsert)
                cursor.execute("""
                    UPDATE knowledge_base
                    SET answer = %s,
                        category = %s,
                        updated_at = NOW()
                    WHERE question = %s
                """, (answer, category, question))
                logging.info(f"🔁 Pergunta existente atualizada: {question}")
                action = "updated"
            else:
                # Insere novo registro
                cursor.execute("""
                    INSERT INTO knowledge_base (question, answer, category, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (question, answer, category))
                logging.info(f"✨ Nova pergunta ensinada: {question}")
                action = "inserted"

            # 🧹 Atualiza o status da pergunta em unknown_questions
            cursor.execute("""
                UPDATE unknown_questions
                SET status = 'answered'
                WHERE question = %s
            """, (question,))

            conn.commit()
            return jsonify({
                "success": True,
                "message": f"IA ensinada com sucesso ({action})."
            }), 200

        except Exception as e:
            logging.exception("❌ Erro em /api/ia/teach:")
            if conn:
                conn.rollback()
            return jsonify({"error": str(e)}), 500

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ============================================================
    # 🆕 NOVO: Stats da IA para Dashboard WhatsApp
    # ============================================================
    @app.route('/api/ia/stats', methods=['GET'])
    def ia_stats():
        """
        Retorna estatísticas da IA + anti-spam para o painel de métricas.
        Usado pelo frontend /app/whatsapp para exibir cards e gráficos.
        """
        try:
            conn = get_db_connection()
            if not conn:
                raise Exception("get_db_connection() retornou None")
            
            cursor = conn.cursor()
            
            # 📊 Stats do knowledge_base
            cursor.execute("SELECT COUNT(*) as total FROM knowledge_base")
            kb_total = cursor.fetchone().get('total', 0)
            
            # 📊 Stats de training_pairs
            cursor.execute("SELECT COUNT(*) as total FROM training_pairs")
            train_total = cursor.fetchone().get('total', 0)
            
            # 📊 Stats de unknown_questions
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN status='pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status='answered' THEN 1 END) as answered
                FROM unknown_questions
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """)
            unknown_stats = cursor.fetchone()
            
            # 📊 Stats da fila_envios (hoje)
            cursor.execute("""
                SELECT 
                    COUNT(CASE WHEN status='enviado' THEN 1 END) as sent,
                    COUNT(CASE WHEN status='falha' THEN 1 END) as failed,
                    COUNT(CASE WHEN status='pendente' THEN 1 END) as pending
                FROM fila_envios
                WHERE DATE(created_at) = CURDATE()
            """)
            queue_stats = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            # 🛡️ Stats do anti-spam controller
            anti_spam = AntiSpamController(os.getenv("ZAPI_INSTANCE"))
            anti_spam_stats = anti_spam.get_daily_stats()
            
            # Calcula taxa de entrega
            sent = queue_stats.get('sent', 0)
            failed = queue_stats.get('failed', 0)
            attempted = sent + failed
            delivery_rate = round((sent / max(attempted, 1)) * 100)
            
            return jsonify({
                "status": "success",
                "timestamp": None,  # Preenchido pelo frontend se necessário
                
                # 🧠 Stats da IA
                "knowledge_base": {
                    "total_questions": kb_total,
                    "training_pairs": train_total
                },
                
                # ❓ Perguntas não respondidas (últimos 7 dias)
                "unknown_questions": {
                    "pending_7d": unknown_stats.get('pending', 0),
                    "answered_7d": unknown_stats.get('answered', 0)
                },
                
                # 📦 Stats da fila (hoje)
                "queue_today": {
                    "sent": sent,
                    "failed": failed,
                    "pending": queue_stats.get('pending', 0),
                    "delivery_rate": delivery_rate
                },
                
                # 🛡️ Stats do anti-spam
                "anti_spam": {
                    "daily_limit": anti_spam_stats.get('daily_limit', 20),
                    "sent": anti_spam_stats.get('sent', 0),
                    "can_send_now": anti_spam_stats.get('can_send_now', True),
                    "next_delay_sec": anti_spam_stats.get('next_delay_sec', 15),
                    "batch_pause_sec": anti_spam_stats.get('batch_pause_sec', 300)
                },
                
                # 🎯 Saúde geral (calculado)
                "health": {
                    "status": "healthy" if delivery_rate >= 95 and anti_spam_stats.get('sent', 0) < 20 else "warning",
                    "message": "🟢 Saudável" if delivery_rate >= 95 else "🟡 Atenção" if delivery_rate >= 80 else "🔴 Crítico"
                }
                
            }), 200
            
        except Exception as e:
            logging.error(f"❌ Erro em /api/ia/stats: {e}", exc_info=True)
            # Retorna estrutura mínima em caso de erro (fail-safe)
            return jsonify({
                "status": "error",
                "message": str(e),
                "anti_spam": {
                    "daily_limit": 20,
                    "sent": 0,
                    "can_send_now": True,
                    "next_delay_sec": 15
                },
                "knowledge_base": {"total_questions": 0, "training_pairs": 0},
                "unknown_questions": {"pending_7d": 0, "answered_7d": 0},
                "queue_today": {"sent": 0, "failed": 0, "pending": 0, "delivery_rate": 100},
                "health": {"status": "unknown", "message": "⚪ Indisponível"}
            }), 200  # Retorna 200 para não quebrar o frontend
