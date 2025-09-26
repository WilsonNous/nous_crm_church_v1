# database_setup.py (adaptado para MySQL)
import os
import pymysql
from contextlib import closing

def criar_tabelas():
    """Cria as tabelas necessárias para o CRM no MySQL do HostGator."""
    queries = [
        '''
        CREATE TABLE IF NOT EXISTS visitantes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            telefone VARCHAR(20) NOT NULL UNIQUE,
            email VARCHAR(255),
            data_nascimento DATE,
            cidade VARCHAR(100),
            genero VARCHAR(20),
            estado_civil VARCHAR(50),
            igreja_atual VARCHAR(100),
            frequenta_igreja TINYINT(1),
            indicacao VARCHAR(100),
            membro VARCHAR(50),
            pedido_oracao TEXT,
            horario_contato VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS status (
            id INT AUTO_INCREMENT PRIMARY KEY,
            visitante_id INT,
            fase_id INT,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE,
            FOREIGN KEY (fase_id) REFERENCES fases(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS fases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            descricao VARCHAR(100) UNIQUE NOT NULL
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS interacoes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            visitante_id INT,
            tipo VARCHAR(50),
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            observacao TEXT,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS eventos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            data DATE,
            descricao TEXT
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            senha VARCHAR(255) NOT NULL,
            tipo_usuario VARCHAR(50) NOT NULL
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS log_mensagens (
            id INT AUTO_INCREMENT PRIMARY KEY,
            visitante_id INT,
            mensagem TEXT NOT NULL,
            status VARCHAR(50),
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS estatisticas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            numero VARCHAR(20) NOT NULL,
            estado_atual VARCHAR(50) NOT NULL,
            proximo_estado VARCHAR(50) NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS conversas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            visitante_id INT,
            mensagem TEXT NOT NULL,
            message_sid VARCHAR(255),
            tipo VARCHAR(50),
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        '''
    ]

    fases_iniciais = [
        "INICIO",
        "MENU",
        "BATIZADO",
        "INTERESSE_DISCIPULADO",
        "INTERESSE_NOVO_COMEC",
        "PEDIDO_ORACAO",
        "OUTRO",
        "FIM",
        "HORARIOS",
        "LINK_WHATSAPP"
    ]

    try:
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            db=os.getenv('MYSQL_DB', ''),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with closing(conn.cursor()) as cursor:
            # Criar tabelas
            for query in queries:
                cursor.execute(query)

            # Inserir fases iniciais se não existirem
            cursor.execute('SELECT COUNT(*) as count FROM fases')
            count = cursor.fetchone()['count']
            if count == 0:
                for fase in fases_iniciais:
                    cursor.execute('INSERT INTO fases (descricao) VALUES (%s)', (fase,))
                print("Fases inseridas com sucesso!")

            conn.commit()
        conn.close()
        print("Tabelas e fases criadas/validadas com sucesso no MySQL!")
    except Exception as e:
        print(f"Erro ao criar tabelas: {e}")


if __name__ == '__main__':
    criar_tabelas()
