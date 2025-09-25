import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import re
import unicodedata
from database import (obter_pares_treinamento, salvar_par_treinamento,
                      obter_perguntas_pendentes, marcar_pergunta_como_respondida)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IAIntegracao:
    def __init__(self):
        """
        Inicializa a IA de Integração.
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
        Normaliza o texto para comparação.
        """
        if not isinstance(texto, str):
            return ""
        texto = texto.strip().lower()
        # Remove acentos
        texto = ''.join(
            c for c in unicodedata.normalize('NFD', texto)
            if unicodedata.category(c) != 'Mn'
        )
        # Remove pontuação e caracteres especiais, mantendo apenas letras, números e espaços
        texto = re.sub(r'[^a-zA-Z0-9\s]', ' ', texto)
        # Remove palavras muito curtas (artigos, preposições)
        palavras = texto.split()
        palavras_filtradas = [p for p in palavras if len(p) > 2]
        return ' '.join(palavras_filtradas)

    def carregar_dados_do_banco(self):
        """
        Carrega os pares de pergunta e resposta do banco de dados MySQL usando o database.py.
        """
        perguntas = []
        respostas = []

        try:
            pares = obter_pares_treinamento()

            for par in pares:
                pergunta = self.normalizar_texto(par['question'])
                resposta = par['answer']
                # Filtros para evitar treinar com dados ruins
                if len(pergunta.split()) > 2 and pergunta not in ["sim", "não", "nao", "obrigado",
                                                                  "obrigada", "valeu", "ok"]:
                    perguntas.append(pergunta)
                    respostas.append(resposta)

            logger.info(f"Carregados {len(perguntas)} pares de treinamento do banco de dados.")

        except Exception as e:
            logger.error(f"Erro ao carregar dados do banco: {e}")
            # Conjunto de fallback robusto
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
                "pastor", "quem sao os pastores", "21 dias de oracao"
            ]
            respostas = [
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso Discipulado de Novos Membros. "
                "Aqui está o link para se inscrever: https://forms.gle/qdxNnPyCfKoJeseU8.   "
                "Estamos muito felizes com seu interesse em se tornar parte da nossa família espiritual!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado, "
                "recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA.   "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado, "
                "recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA.   "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado, "
                "recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA.   "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Seguem nossos horários de cultos:\n🌿 Domingo - Culto da Família - às 19h\n"
                "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção."
                " \"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*"
                "\n🔥 Quinta Fé - Culto dos Milagres - às 20h\nUm encontro de fé para vivermos o sobrenatural de Deus."
                " \"Tudo é possível ao que crê.\" *(Marcos 9:23)*\n🎉 Sábado - Culto Alive - às 20h"
                "\nJovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis."
                "\" *(1 Timóteo 4:12)*\n🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles."
                "\" *(Mateus 18:20)*\nGostaria de mais informações?",
                "Seguem nossos horários de cultos:\n🌿 Domingo - Culto da Família - às 19h"
                "\nUma oportunidade de estar em comunhão com sua família, "
                "adorando a Deus e agradecendo por cada bênção. \"Eu e a minha casa serviremos ao Senhor."
                "\" *(Josué 24:15)*\n🔥 Quinta Fé - Culto dos Milagres - às 20h"
                "\nUm encontro de fé para vivermos o sobrenatural de Deus. \"Tudo é possível ao que crê."
                "\" *(Marcos 9:23)*\n🎉 Sábado - Culto Alive - às 20h"
                "\nJovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis."
                "\" *(1 Timóteo 4:12)*\n🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles."
                "\" *(Mateus 18:20)*\nGostaria de mais informações?",
                "Seguem nossos horários de cultos:\n🌿 Domingo - Culto da Família - às 19h"
                "\nUma oportunidade de estar em comunhão com sua família, "
                "adorando a Deus e agradecendo por cada bênção. \"Eu e a minha casa serviremos ao Senhor."
                "\" *(Josué 24:15)*\n🔥 Quinta Fé - Culto dos Milagres - às 20h"
                "\nUm encontro de fé para vivermos o sobrenatural de Deus. \"Tudo é possível ao que crê."
                "\" *(Marcos 9:23)*\n🎉 Sábado - Culto Alive - às 20h"
                "\nJovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*"
                "\n🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles."
                "\" *(Mateus 18:20)*\nGostaria de mais informações?",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "\nAgradecemos seu contato e esperamos vê-lo em breve!",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "\nAgradecemos seu contato e esperamos vê-lo em breve!",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "\nAgradecemos seu contato e esperamos vê-lo em breve!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Paz de Cristo, somos os Homens Corajosos da Mais de Cristo Canasvieiras, "
                "nossa missão é servir a Deus com toda força e coração, "
                "nos colocando a frente dos propósitos de Deus, para sermos, "
                "sacerdotes da nossa casa, homens de coragem e temente a Deus."
                "\nVenha fazer parte deste exército e ficar mais próximo do seu propósito."
                "\nSegue link do grupo de whatsapp: https://chat.whatsapp.com/H4pFqtsruDr0QJ1NvCMjda  ",
                "Paz de Cristo, somos o Ministério Mulheres Transformadas da Mais de Cristo Canasvieiras. "
                "Nosso objetivo é promover o crescimento espiritual das mulheres, "
                "fortalecendo nossa fé e nos unindo em amor e comunhão. "
                "Temos encontros mensais cheios de aprendizado e inspiração."
                "\nVenha fazer parte deste grupo e viver os propósitos que Deus tem para sua vida."
                "\nSegue link do grupo de whatsapp: https://chat.whatsapp.com/LT0pN2SPTqf66yt3AWKIAe  ",
                "O Ministério Alive é dedicado aos jovens e adolescentes, com cultos vibrantes e cheios de propósito.",
                "Nossos pastores atuais são:\n- *Pr Fábio Ferreira*\n- *Pra Cláudia Ferreira*"
                "\nVocê pode seguir o *_Pr Fábio Ferreira_* no Instagram: _@prfabioferreirasoficial_"
                "\nE a *_Pra Cláudia Ferreira_* no Instagram: _@claudiaferreiras1_",
                "Nossos pastores atuais são:\n- *Pr Fábio Ferreira*\n- *Pra Cláudia Ferreira*"
                "\nVocê pode seguir o *_Pr Fábio Ferreira_* no Instagram: _@prfabioferreirasoficial_"
                "\nE a *_Pra Cláudia Ferreira_* no Instagram: _@claudiaferreiras1_",
                "Olá! Ficamos felizes com seu interesse nos 21 dias de oração. 🙏 "
                "Este evento acontece diariamente, das 23h às 23:30, na igreja, e seguirá até o dia 20 de novembro."
                "Se será um tempo especial para buscar paz, inspiração e fortalecer a fé. "
                "Caso precise de mais informações ou queira confirmar presença, estou aqui para ajudar!",
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
        logger.info(f"Melhor correspondência: '{self.perguntas_treinadas[indice_mais_similar]}' "
                    f"com confiança {confianca:.2f}")

        if confianca >= limiar_confianca:
            resposta = self.respostas_treinadas[indice_mais_similar]
            return resposta, confianca
        else:
            return None, confianca

    def ensinar_ia(self, pergunta: str, resposta: str, categoria: str = 'geral'):
        """
        Ensina a IA com um novo par de pergunta e resposta.
        """
        try:
            # Salva o par no banco de dados
            if salvar_par_treinamento(pergunta, resposta, categoria):
                logger.info(f"IA ensinada com sucesso: {pergunta} -> {resposta}")
                # Marca a pergunta como respondida
                marcar_pergunta_como_respondida(pergunta)
                # Recarrega e retreina o modelo
                self.carregar_e_treinar()
                return True
            else:
                logger.error(f"Erro ao salvar par de treinamento: {pergunta}")
                return False
        except Exception as e:
            logger.error(f"Erro ao ensinar IA: {e}")
            return False

    @staticmethod
    def obter_perguntas_pendentes():
        """
        Retorna as perguntas pendentes para treinamento.
        """
        return obter_perguntas_pendentes()


# --- Exemplo de Uso e Teste ---

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
