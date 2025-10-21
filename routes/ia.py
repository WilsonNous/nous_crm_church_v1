import logging
from flask import request, jsonify, render_template, session, redirect, url_for
from database import get_db_connection

def register(app):
    @app.route('/admin/integra/learn')
    def integra_learn_dashboard():
        if not session.get('integra_admin_logged_in'):
            return redirect(url_for('login_page'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, question, created_at FROM unknown_questions WHERE status='pending' ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        questions = [{"id": r[0], "user_id": r[1], "question": r[2], "created_at": r[3]} for r in rows]
        cursor.close(); conn.close()
        return render_template('admin_integra_learn.html', questions=questions)

    @app.route('/api/ia/pending-questions', methods=['GET'])
    def ia_pending_questions():
        try:
            logging.info("🧩 Iniciando /api/ia/pending-questions")
            conn = get_db_connection()
            logging.info(f"🔍 Tipo da conexão: {type(conn)}")
            if not conn:
                raise Exception("get_db_connection() retornou None")
    
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, question, created_at FROM unknown_questions WHERE status='pending'")
            rows = cursor.fetchall()
            perguntas = [{"id": r[0], "user_id": r[1], "question": r[2], "created_at": r[3]} for r in rows]
            cursor.close(); conn.close()
            logging.info(f"✅ Total perguntas: {len(perguntas)}")
            return jsonify({"questions": perguntas}), 200
    
        except Exception as e:
            logging.exception("❌ Erro em /api/ia/pending-questions:")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/ia/teach', methods=['POST'])
    def ia_teach():
        try:
            data = request.get_json()
            question = data.get('question')
            answer = data.get('answer')
            category = data.get('category')
    
            if not all([question, answer, category]):
                return jsonify({"error": "Campos obrigatórios ausentes."}), 400
    
            conn = get_db_connection()
            cursor = conn.cursor()
    
            # Atualiza pergunta na base e adiciona ao conhecimento
            cursor.execute("""
                UPDATE unknown_questions SET status='answered' WHERE question=%s
            """, (question,))
            cursor.execute("""
                INSERT INTO knowledge_base (question, answer, category, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (question, answer, category))
            conn.commit()
            cursor.close()
            conn.close()
    
            return jsonify({"success": True}), 200
    
        except Exception as e:
            logging.error(f"Erro em /api/ia/teach: {e}")
            return jsonify({"error": str(e)}), 500
