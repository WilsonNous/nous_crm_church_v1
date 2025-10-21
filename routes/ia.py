import logging
from flask import request, jsonify, render_template, session, redirect, url_for
from database import get_db_connection

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
