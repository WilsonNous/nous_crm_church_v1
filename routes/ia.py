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
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, question, created_at FROM unknown_questions WHERE status='pending'")
            rows = cursor.fetchall()
            cursor.close(); conn.close()
            perguntas = [{"id": r[0], "user_id": r[1], "question": r[2], "created_at": r[3]} for r in rows]
            return jsonify({"questions": perguntas}), 200
        except Exception as e:
            logging.error(f"Erro em /api/ia/pending-questions: {e}")
            return jsonify({"error": str(e)}), 500

