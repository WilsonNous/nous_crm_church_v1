import logging
import mysql.connector
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
import unicodedata

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IAIntegracao:
    def __init__(self, db_config):
        """
        Inicializa a IA de Integração.
        :param db_config: Dicionário com configuração do banco de dados (host, user, password, database)
        """
        self.db_config = db_config
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),  # Considera palavras únicas e pares de palavras
            stop_words=None,     # Você pode adicionar palavras de parada em português aqui
            max_features=5000    # Limita o número de features para otimização
        )
        self.perguntas_treinadas = []
        self.respostas_treinadas = []
        self.modelo_treinado = None
        self.carregar_e_treinar()

    def normalizar_texto(self, texto):
        """
        Normaliza o texto para comparação (remove acentos, converte para minúsculas, etc).
        """
        if not isinstance(texto, str):
            return ""
        texto = texto.strip().lower()
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        # Remove caracteres especiais, mantendo apenas letras, números e espaços
        texto = re.sub(r'[^a-zA-Z0-9\s]', ' ', texto)
        return texto

    def carregar_dados_do_banco(self):
        """
        Carrega os pares de pergunta e resposta do banco de dados MySQL.
        Assume que você tem uma tabela chamada `conversas` ou similar com as colunas:
        - `mensagem` (o texto da mensagem)
        - `tipo` ('recebida' para pergunta do usuário, 'enviada' para resposta do bot)
        - `telefone` (para agrupar conversas por usuário)

        Esta função é um exemplo e DEVE ser adaptada à sua estrutura real de banco de dados.
        """
        perguntas = []
        respostas = []

        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)

            # Consulta para obter pares de pergunta e resposta.
            # Esta é uma lógica simplificada. Em um cenário real, você pode querer
            # agrupar por sessão de conversa ou usar timestamps para emparelhar corretamente.
            query = """
            SELECT 
                c1.mensagem as pergunta,
                c2.mensagem as resposta
            FROM conversas c1
            JOIN conversas c2 ON c1.telefone = c2.telefone 
                AND c2.id > c1.id 
                AND c2.tipo = 'enviada'
            WHERE c1.tipo = 'recebida'
            ORDER BY c1.id, c2.id
            LIMIT 1; -- Remova este LIMIT para carregar todos os dados
            """

            cursor.execute(query)
            resultados = cursor.fetchall()

            for row in resultados:
                pergunta = self.normalizar_texto(row['pergunta'])
                resposta = row['resposta']  # Mantém a resposta original, sem normalizar

                # Filtra perguntas muito curtas ou genéricas
                if len(pergunta.split()) > 2 and pergunta not in ["sim", "não", "nao", "obrigado", "obrigada"]:
                    perguntas.append(pergunta)
                    respostas.append(resposta)

            cursor.close()
            conn.close()

            logger.info(f"Carregados {len(perguntas)} pares de treinamento do banco de dados.")

        except Exception as e:
            logger.error(f"Erro ao carregar dados do banco: {e}")
            # Se falhar, usamos um conjunto de dados de fallback
            perguntas = [
                "que horas e o culto",
                "como me cadastrar",
                "onde fica a igreja",
                "quero entrar no grupo de whatsapp",
                "gostaria de receber oracoes"
            ]
            respostas = [
                "*Seguem nossos horários de cultos:*\n🌿 *Domingo* - Culto da Família - às 19h\n🔥 *Quinta Fé* - Culto dos Milagres - às 20h\n🎉 *Sábado* - Culto Alive - às 20h",
                "Você pode se cadastrar respondendo ao nosso formulário: https://forms.gle/...",
                "Estamos localizados na Rua das Flores, 123, Canasvieiras, Florianópolis/SC.",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: https://chat.whatsapp.com/...",
                "Ficamos honrados em receber o seu pedido de oração. Sinta-se à vontade para compartilhar o que está em seu coração."
            ]
            logger.info("Usando conjunto de dados de fallback.")

        return perguntas, respostas

    def treinar_modelo(self):
        """
        Treina o modelo de similaridade de texto usando TF-IDF.
        """
        if len(self.perguntas_treinadas) == 0:
            logger.warning("Nenhum dado para treinar. O modelo não será treinado.")
            return False

        try:
            # Transforma as perguntas em vetores TF-IDF
            self.modelo_treinado = self.vectorizer.fit_transform(self.perguntas_treinadas)
            logger.info("Modelo treinado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao treinar o modelo: {e}")
            return False

    def carregar_e_treinar(self):
        """
        Função de conveniência que carrega os dados e já treina o modelo.
        """
        self.perguntas_treinadas, self.respostas_treinadas = self.carregar_dados_do_banco()
        self.treinar_modelo()

    def responder_pergunta(self, pergunta_usuario, limiar_confianca=0.3):
        """
        Recebe uma pergunta do usuário e retorna a resposta mais adequada.

        :param pergunta_usuario: A pergunta feita pelo usuário.
        :param limiar_confianca: O valor mínimo de similaridade para considerar uma resposta válida.
        :return: Uma tupla (resposta, confianca) ou (None, 0.0) se nenhuma resposta for encontrada.
        """
        if self.modelo_treinado is None:
            logger.warning("Modelo não treinado. Não é possível responder.")
            return None, 0.0

        # Normaliza a pergunta do usuário
        pergunta_normalizada = self.normalizar_texto(pergunta_usuario)

        # Transforma a pergunta do usuário em um vetor
        try:
            vetor_pergunta = self.vectorizer.transform([pergunta_normalizada])
        except Exception as e:
            logger.error(f"Erro ao transformar a pergunta do usuário: {e}")
            return None, 0.0

        # Calcula a similaridade com todas as perguntas treinadas
        similaridades = cosine_similarity(vetor_pergunta, self.modelo_treinado).flatten()

        # Encontra o índice da pergunta mais similar
        indice_mais_similar = np.argmax(similaridades)
        confianca = similaridades[indice_mais_similar]

        logger.info(f"Pergunta do usuário: '{pergunta_usuario}'")
        logger.info(f"Melhor correspondência: '{self.perguntas_treinadas[indice_mais_similar]}' com confiança {confianca:.2f}")

        if confianca >= limiar_confianca:
            resposta = self.respostas_treinadas[indice_mais_similar]
            return resposta, confianca
        else:
            return None, confianca

# --- Exemplo de Uso e Teste ---

if __name__ == "__main__":
    # Substitua estas configurações pelas do seu banco de dados real
    config_db = {
        'host': 'localhost',
        'user': 'seu_usuario',
        'password': 'sua_senha',
        'database': 'seu_banco'
    }

    # Cria uma instância da IA
    ia = IAIntegracao(config_db)

    # Testa com algumas perguntas
    testes = [
        "Que horas é o culto de domingo?",
        "Como faço para me cadastrar?",
        "Me fale sobre o grupo de whatsapp",
        "Onde vocês ficam?"
    ]

    for pergunta in testes:
        resposta, confianca = ia.responder_pergunta(pergunta)
        if resposta:
            print(f"\nPergunta: {pergunta}")
            print(f"Resposta: {resposta}")
            print(f"Confiança: {confianca:.2f}")
        else:
            print(f"\nPergunta: {pergunta} -> Nenhuma resposta encontrada (Confiança: {confianca:.2f})")
