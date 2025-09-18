import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
import unicodedata

# --- IMPORTAÇÕES DE CONSTANTE ---
from constantes import mensagens, EstadoVisitante, palavras_chave_ministerios
from database import get_db_connection

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IAIntegracao:
    def __init__(self):
        """
        Inicializa a IA de Integração.
        Não é necessário passar configurações, pois usaremos o database.py existente.
        """
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

    @staticmethod
    def normalizar_texto(texto):
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
        Carrega os pares de pergunta e resposta da tabela 'training_pairs'.
        Se a tabela estiver vazia, extrai pares da tabela 'conversas' e os salva em 'training_pairs'.
        """
        perguntas = []
        respostas = []

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # --- PASSO 1: Tenta carregar dos pares já salvos (training_pairs) ---
            cursor.execute("SELECT pergunta, resposta FROM training_pairs ORDER BY id")
            pares_salvos = cursor.fetchall()

            if pares_salvos:
                for row in pares_salvos:
                    pergunta = self.normalizar_texto(row['pergunta'])
                    resposta = row['resposta']
                    perguntas.append(pergunta)
                    respostas.append(resposta)
                logger.info(f"Carregados {len(pares_salvos)} pares de treinamento da tabela 'training_pairs'.")
                cursor.close()
                conn.close()
                return perguntas, respostas

            # --- PASSO 2: Se 'training_pairs' estiver vazia, extrai da tabela 'conversas' ---
            logger.info("Tabela 'training_pairs' vazia. Extraindo pares da tabela 'conversas'...")

            query_conversas = """
            SELECT 
                c1.visitante_id,
                c1.mensagem as pergunta,
                c2.mensagem as resposta,
                c1.data_hora as data_pergunta,
                c2.data_hora as data_resposta
            FROM conversas c1
            JOIN conversas c2 
                ON c1.visitante_id = c2.visitante_id 
                AND c2.data_hora > c1.data_hora
                AND c2.tipo = 'enviada'
            WHERE c1.tipo = 'recebida'
            ORDER BY c1.visitante_id, c1.data_hora, c2.data_hora
            """

            cursor.execute(query_conversas)
            resultados = cursor.fetchall()

            # Dicionário para rastrear a última pergunta de cada visitante
            ultima_pergunta_por_visitante = {}

            for row in resultados:
                visitante_id = row['visitante_id']
                pergunta = self.normalizar_texto(row['pergunta'])
                resposta = row['resposta']  # Mantém a resposta original

                # Verifica se esta é a resposta mais próxima da pergunta
                if visitante_id not in ultima_pergunta_por_visitante:
                    ultima_pergunta_por_visitante[visitante_id] = {
                        'pergunta': pergunta,
                        'resposta': resposta,
                        'data_pergunta': row['data_pergunta']
                    }
                else:
                    # Se já havia uma pergunta anterior, adicionamos o par ao dataset
                    pergunta_anterior = ultima_pergunta_por_visitante[visitante_id]['pergunta']
                    resposta_anterior = ultima_pergunta_por_visitante[visitante_id]['resposta']

                    # Filtros para evitar treinar com dados ruins
                    if len(pergunta_anterior.split()) > 2 and pergunta_anterior not in ["sim", "não", "nao", "obrigado",
                                                                                        "obrigada", "valeu", "ok"]:
                        perguntas.append(pergunta_anterior)
                        respostas.append(resposta_anterior)

                    # Atualiza para a nova pergunta
                    ultima_pergunta_por_visitante[visitante_id] = {
                        'pergunta': pergunta,
                        'resposta': resposta,
                        'data_pergunta': row['data_pergunta']
                    }

            # Adiciona o último par de cada visitante
            for item in ultima_pergunta_por_visitante.values():
                pergunta = item['pergunta']
                resposta = item['resposta']
                if len(pergunta.split()) > 2 and pergunta not in ["sim", "não", "nao", "obrigado", "obrigada", "valeu",
                                                                  "ok"]:
                    perguntas.append(pergunta)
                    respostas.append(resposta)

            # --- PASSO 3: Salva os pares extraídos na tabela 'training_pairs' ---
            if perguntas:
                for i in range(len(perguntas)):
                    try:
                        cursor.execute(
                            "INSERT IGNORE INTO training_pairs (pergunta, resposta, "
                            "fonte, categoria) VALUES (%s, %s, %s, %s)",
                            (perguntas[i], respostas[i], 'conversa_bot', 'geral')
                        )
                    except Exception as e:
                        logger.error(f"Erro ao salvar par no banco: {e}")

                conn.commit()
                logger.info(f"Salvos {len(perguntas)} novos pares de treinamento na tabela 'training_pairs'.")

            cursor.close()
            conn.close()

            logger.info(f"Carregados {len(perguntas)} pares de treinamento da tabela 'conversas'.")

        except Exception as e:
            logger.error(f"Erro ao carregar dados do banco: {e}")
            # Conjunto de fallback robusto
            perguntas, respostas = self.get_fallback_dataset()

        return perguntas, respostas

    def get_fallback_dataset(self):
        """
        Retorna um conjunto de dados de fallback robusto.
        """
        perguntas = [
            "sou batizado o que tem na igreja",
            "sou batizado o que a igreja oferece",
            "sou batizado quais atividades",
            "sou batizado", "quero me tornar membro", "batizado em aguas",
            "nao sou batizado", "quero me tornar membro", "novo comeco",
            "pedido de oracao", "receber oracoes", "orar por mim",
            "horarios dos cultos", "que horas e o culto", "culto de domingo",
            "grupo whatsapp", "entrar no grupo", "link do grupo",
            "outro assunto", "falar com secretaria", "ajuda",
            "homens corajosos", "mulheres transformadas", "ministerio jovens",
            "pastor", "quem sao os pastores", "21 dias de oracao",
            "onde fica a igreja", "qual o endereco", "localizacao da igreja"
        ]
        respostas = [
            "Que ótimo! Como você já é batizado, você pode participar do nosso Discipulado de Novos Membros, "
            "dos Grupos de Comunhão (GC) e de todos os ministérios da casa (Homens Corajosos, Mulheres Transformadas, "
            "Ministério Jovem, etc.). Aqui está o link para se inscrever "
            "no Discipulado: https://forms.gle/qdxNnPyCfKoJeseU8",
            "Que ótimo! Como você já é batizado, você pode participar do nosso Discipulado de Novos Membros, "
            "dos Grupos de Comunhão (GC) e de todos os ministérios da casa (Homens Corajosos, Mulheres Transformadas, "
            "Ministério Jovem, etc.). Aqui está o link para se inscrever "
            "no Discipulado: https://forms.gle/qdxNnPyCfKoJeseU8",
            "Que ótimo! Como você já é batizado, você pode participar do nosso Discipulado de Novos Membros, "
            "dos Grupos de Comunhão (GC) e de todos os ministérios da casa (Homens Corajosos, Mulheres Transformadas, "
            "Ministério Jovem, etc.). Aqui está o link para se inscrever "
            "no Discipulado: https://forms.gle/qdxNnPyCfKoJeseU8",
            mensagens[EstadoVisitante.INTERESSE_DISCIPULADO],
            mensagens[EstadoVisitante.INTERESSE_DISCIPULADO],
            mensagens[EstadoVisitante.INTERESSE_DISCIPULADO],
            mensagens[EstadoVisitante.INTERESSE_NOVO_COMEC],
            mensagens[EstadoVisitante.INTERESSE_NOVO_COMEC],
            mensagens[EstadoVisitante.INTERESSE_NOVO_COMEC],
            "Ficamos honrados em receber o seu pedido de oração. "
            "Sinta-se à vontade para compartilhar o que está em seu coração.",
            "Ficamos honrados em receber o seu pedido de oração. "
            "Sinta-se à vontade para compartilhar o que está em seu coração.",
            "Ficamos honrados em receber o seu pedido de oração. "
            "Sinta-se à vontade para compartilhar o que está em seu coração.",
            mensagens[EstadoVisitante.HORARIOS],
            mensagens[EstadoVisitante.HORARIOS],
            mensagens[EstadoVisitante.HORARIOS],
            mensagens[EstadoVisitante.LINK_WHATSAPP],
            mensagens[EstadoVisitante.LINK_WHATSAPP],
            mensagens[EstadoVisitante.LINK_WHATSAPP],
            mensagens[EstadoVisitante.OUTRO],
            mensagens[EstadoVisitante.OUTRO],
            mensagens[EstadoVisitante.OUTRO],
            palavras_chave_ministerios["homens"],
            palavras_chave_ministerios["mulheres"],
            palavras_chave_ministerios["jovens"],
            palavras_chave_ministerios["pastor"],
            palavras_chave_ministerios["pastor"],
            palavras_chave_ministerios["21 dias"],
            "Estamos localizados na Rua das Flores, 123, Canasvieiras, Florianópolis/SC.",
            "Estamos localizados na Rua das Flores, 123, Canasvieiras, Florianópolis/SC.",
            "Estamos localizados na Rua das Flores, 123, Canasvieiras, Florianópolis/SC."
        ]
        logger.info("Usando conjunto de dados de fallback robusto.")
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
        logger.info(f"Melhor correspondência: '{self.perguntas_treinadas[indice_mais_similar]}' com confiança"
                    f" {confianca:.2f}")

        if confianca >= limiar_confianca:
            resposta = self.respostas_treinadas[indice_mais_similar]
            return resposta, confianca
        else:
            return None, confianca

    def recarregar_e_treinar(self):
        """
        Força a recarga dos dados do banco e retreina o modelo.
        Útil para quando novos pares são adicionados manualmente à tabela 'training_pairs'.
        """
        logger.info("Recarregando dados e retreinando o modelo...")
        self.perguntas_treinadas, self.respostas_treinadas = self.carregar_dados_do_banco()
        self.treinar_modelo()
        logger.info("Modelo recarregado e treinado com sucesso.")


if __name__ == "__main__":
    # Cria uma instância da IA
    ia = IAIntegracao()

    # Testa com algumas perguntas
    testes = [
        "Que horas é o culto de domingo?",
        "Como faço para me cadastrar?",
        "Me fale sobre o grupo de whatsapp",
        "Onde vocês ficam?",
        "Quero falar com a secretaria",
        "Gostaria de receber orações"
    ]

    for pergunta in testes:
        resposta, confianca = ia.responder_pergunta(pergunta)
        if resposta:
            print(f"\nPergunta: {pergunta}")
            print(f"Resposta: {resposta}")
            print(f"Confiança: {confianca:.2f}")
        else:
            print(f"\nPergunta: {pergunta} -> Nenhuma resposta encontrada (Confiança: {confianca:.2f})")
