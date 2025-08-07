import sqlite3
from contextlib import closing


# Função para obter a conexão com o banco de dados
def get_db_connection():
    try:
        conn = sqlite3.connect('crm_visitantes.db')  # Altere se o caminho for diferente no Heroku
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        raise


# Função para salvar visitante
def salvar_visitante(nome, telefone, email, data_nascimento, cidade, genero,
                     estado_civil, igreja_atual, frequenta_igreja, indicacao,
                     membro, pedido_oracao, horario_contato):
    """Salva um visitante no banco de dados."""
    try:
        with closing(get_db_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute(''' 
                INSERT INTO visitantes (nome, telefone, email, data_nascimento,
                 cidade, genero, estado_civil, igreja_atual,
                 frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome, telefone, email, data_nascimento, cidade, genero, estado_civil,
                  igreja_atual, frequenta_igreja, indicacao, membro, pedido_oracao, horario_contato))
            conn.commit()
        print("Visitante cadastrado com sucesso!")
        return True
    except sqlite3.IntegrityError:
        print(f"Erro: O telefone {telefone} já está cadastrado.")
        return False
    except sqlite3.Error as e:
        print(f"Erro ao salvar visitante: {e}")
        return False


# Teste de inserção de visitante
if __name__ == '__main__':
    visitante_data = {
        'nome': 'John Doe',
        'telefone': '11987654321',
        'email': 'johndoe@example.com',
        'data_nascimento': '1990-01-01',
        'cidade': 'São Paulo',
        'genero': 'Masculino',
        'estado_civil': 'Solteiro',
        'igreja_atual': 'Igreja Central',
        'frequenta_igreja': 1,  # 1 para frequenta, 0 para não
        'indicacao': 'Amigo',
        'membro': 'Não',
        'pedido_oracao': 'Oração pela família',
        'horario_contato': 'Manhã'
    }

    salvar_visitante(**visitante_data)
