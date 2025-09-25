# Importações de bibliotecas padrão
import logging
import os

# Importações de bibliotecas externas
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Importações de módulos internos
from routes import register_routes

# Configurações do Flask
app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)


register_routes(app)


@app.route('/visitor_form')
def visitor_form():
    """Rota para retornar o formulário HTML de visitantes."""
    return send_from_directory('templates/', 'login.html')


# Configuração de logs
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # O Heroku fornece a variável de ambiente PORT
    app.run(host='0.0.0.0', port=port, debug=True)  # Habilitar o modo debug
