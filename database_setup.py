import sqlite3
from contextlib import closing

DB_PATH = 'crm_visitantes.db'


def criar_tabelas():
    """Cria as tabelas necessárias para o CRM de Visitantes."""
    queries = [
        '''
        CREATE TABLE IF NOT EXISTS visitantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL UNIQUE,
            email TEXT,
            data_nascimento TEXT,
            cidade TEXT,
            genero TEXT,
            estado_civil TEXT,
            igreja_atual TEXT,
            frequenta_igreja INTEGER CHECK(frequenta_igreja IN (0, 1)),
            indicacao TEXT,
            membro TEXT,
            pedido_oracao TEXT,
            horario_contato TEXT
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitante_id INTEGER,
            fase_id INTEGER,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE,
            FOREIGN KEY (fase_id) REFERENCES fases(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS fases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL UNIQUE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS interacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitante_id INTEGER,
            tipo TEXT,  -- Tipo de interação: mensagem, ligação, visita etc.
            data_hora TEXT,
            observacao TEXT,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data TEXT,
            descricao TEXT
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,  -- Senha deve ser armazenada com hash
            tipo_usuario TEXT NOT NULL  -- admin, pastor, etc.
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS log_mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitante_id INTEGER,
            mensagem TEXT NOT NULL,
            status TEXT,  -- Enviada, Recebida, Falha, etc.
            data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS estatisticas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT NOT NULL,
            estado_atual TEXT NOT NULL,
            proximo_estado TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS conversas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitante_id INTEGER,
            mensagem TEXT NOT NULL,
            message_sid TEXT,
            tipo TEXT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
        )
        '''
    ]

    indices = [
        "CREATE INDEX IF NOT EXISTS idx_visitante_id ON status(visitante_id)",
        "CREATE INDEX IF NOT EXISTS idx_visitante_id_interacoes ON interacoes(visitante_id)"
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
        with closing(sqlite3.connect(DB_PATH)) as conn:
            cursor = conn.cursor()

            # Criar tabelas
            for query in queries:
                cursor.execute(query)

            # Criar índices
            for index_query in indices:
                cursor.execute(index_query)

            # Inserir as fases iniciais se ainda não estiverem na tabela
            cursor.execute('SELECT COUNT(*) FROM fases')
            count = cursor.fetchone()[0]
            if count == 0:
                for fase in fases_iniciais:
                    cursor.execute('INSERT INTO fases (descricao) VALUES (?)', (fase,))
                print("Fases inseridas com sucesso!")

            conn.commit()
        print("Tabelas, índices e fases criados com sucesso!")
    except sqlite3.Error as e:
        print(f"Erro ao criar tabelas e índices: {e}")


if __name__ == '__main__':
    criar_tabelas()
