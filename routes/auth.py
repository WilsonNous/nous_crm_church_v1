import os
from flask import request, jsonify
from werkzeug.security import check_password_hash

try:
    from flask_jwt_extended import create_access_token
except Exception:
    def create_access_token(identity): return f"MOCK_TOKEN_FOR_{identity}"

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", None)

def register(app):
    @app.route('/api/login', methods=['POST'])
    def login():
        data = request.get_json()
        if not data:
            return jsonify({'status': 'failed', 'message': 'Nenhum dado foi fornecido'}), 400

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'status': 'failed', 'message': 'Usuário e senha são obrigatórios'}), 400

        if username == ADMIN_USER:
            if ADMIN_PASSWORD_HASH:
                if not check_password_hash(ADMIN_PASSWORD_HASH, password):
                    return jsonify({'status': 'failed', 'message': 'Senha inválida'}), 401
            else:
                if password != "s3cr3ty":
                    return jsonify({'status': 'failed', 'message': 'Senha inválida'}), 401

            token = create_access_token(identity={'username': username, 'role': 'admin'})
            return jsonify({'status': 'success', 'message': 'Login bem-sucedido!', 'token': token}), 200

        return jsonify({'status': 'failed', 'message': 'Usuário inválido'}), 401
