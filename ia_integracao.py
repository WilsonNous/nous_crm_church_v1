import logging
import re
import unicodedata
from database import get_db_connection

# --- CORRIGIDO: Importação necessária ---
from flask import jsonify

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IAIntegracao:
    def __init__(self):
        """
        Inicializa a IA de Integração.
        """
        pass

    def responder_pergunta(self, pergunta_usuario: str, numero_usuario: str, ultima_pergunta: str = None) -> dict:
        """
        Recebe uma pergunta do usuário e retorna a resposta mais adequada.

        :param pergunta_usuario: A pergunta feita pelo usuário.
        :param numero_usuario: O número de telefone do usuário.
        :param ultima_pergunta: A última pergunta feita pelo usuário (para contexto).
        :return: Um dicionário com a resposta, a intenção e a confiança.
        """
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            if not conn:
                return {'response': 'Erro de conexão com o banco de dados.', 'intent': 'error', 'confidence': 0.0}

            # --- CORRIGIDO: Cursor compatível com pymysql ---
            cursor = conn.cursor()

            pergunta_normalizada = self.normalizar_texto(pergunta_usuario)

            # --- DETECÇÃO DE CONTEXTO ---
            intencao_atual = None
            if ultima_pergunta:
                if 'discipulado' in ultima_pergunta.lower():
                    intencao_atual = 'discipulado'
                elif 'ministério' in ultima_pergunta.lower() or 'ministerio' in ultima_pergunta.lower():
                    intencao_atual = 'ministerios'
                elif 'batismo' in ultima_pergunta.lower():
                    intencao_atual = 'batismo'
                elif 'culto' in ultima_pergunta.lower() or 'horário' in ultima_pergunta.lower():
                    intencao_atual = 'horarios'

            # --- BUSCA POR INTENÇÃO ---
            resposta = None
            intent = 'geral'
            confidence = 0.0

            if intencao_atual:
                cursor.execute("""
                    SELECT answer, category FROM knowledge_base 
                    WHERE category = %s AND (question LIKE %s OR keywords LIKE %s)
                    ORDER BY updated_at DESC LIMIT 1
                """, (intencao_atual, f'%{pergunta_normalizada}%', f'%{pergunta_normalizada}%'))
                result = cursor.fetchone()
                if result:
                    # --- CORRIGIDO: Acesso por índice em vez de chave ---
                    resposta = result[0]  # answer
                    intent = result[1]  # category
                    confidence = 0.9

            # --- BUSCA GERAL ---
            if not resposta:
                cursor.execute("""
                    SELECT answer, category FROM knowledge_base 
                    WHERE question LIKE %s OR keywords LIKE %s 
                    ORDER BY updated_at DESC LIMIT 1
                """, (f'%{pergunta_normalizada}%', f'%{pergunta_normalizada}%'))
                result = cursor.fetchone()
                if result:
                    # --- CORRIGIDO: Acesso por índice em vez de chave ---
                    resposta = result[0]  # answer
                    intent = result[1]  # category
                    confidence = 0.8

            # --- APRENDIZADO ATIVO ---
            if not resposta:
                # Registra a pergunta não respondida
                cursor.execute("""
                    INSERT INTO unknown_questions (user_id, question, status)
                    VALUES (%s, %s, 'pending')
                """, (numero_usuario, pergunta_usuario[:255]))
                conn.commit()
                resposta = "Desculpe, ainda não sei responder isso. Posso te encaminhar para a secretaria?"
                intent = 'unknown'
                confidence = 0.1

            return {
                'response': resposta,
                'intent': intent,
                'confidence': confidence
            }

        except Exception as e:
            logger.error(f"Erro ao responder pergunta: {e}")
            return {'response': 'Desculpe, ocorreu um erro interno. Tente novamente mais tarde.',
                    'intent': 'error', 'confidence': 0.0}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

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

    # --- CORRIGIDO: Função carregar_dados_do_banco ---
    def carregar_dados_do_banco(self):
        """
        Carrega os pares de pergunta e resposta da tabela 'training_pairs'.
        """
        perguntas = []
        respostas = []

        try:
            conn = get_db_connection()
            if not conn:
                # --- CORRIGIDO: Retorno correto em caso de erro ---
                return [], []

            # --- CORRIGIDO: Cursor compatível com pymysql ---
            cursor = conn.cursor()

            # --- CORRIGIDO: Query adaptada para a tabela 'training_pairs' ---
            cursor.execute("""
                SELECT question, answer FROM training_pairs 
                ORDER BY id DESC LIMIT 1000
            """)
            pares = cursor.fetchall()
            cursor.close()
            conn.close()

            for row in pares:
                # --- CORRIGIDO: Acesso por índice em vez de chave ---
                pergunta = self.normalizar_texto(row[0])  # question
                resposta = row[1]  # answer
                # Filtros para evitar treinar com dados ruins
                if len(pergunta.split()) > 2 and pergunta not in ["sim", "não", "nao", "obrigado",
                                                                  "obrigada", "valeu", "ok"]:
                    perguntas.append(pergunta)
                    respostas.append(resposta)

            logger.info(f"Carregados {len(perguntas)} pares de treinamento da tabela 'training_pairs'.")

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
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Que ótimo! Como você já foi batizado, você pode participar do nosso "
                "Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                "https://forms.gle/qdxNnPyCfKoJeseU8.   Estamos muito felizes com seu interesse em se tornar "
                "parte da nossa família espiritual!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado,"
                " recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA. "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado,"
                " recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA. "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos felizes com o seu interesse! Como você ainda não foi batizado,"
                " recomendamos que participe do nosso Discipulado Novo Começo, "
                "onde você aprenderá mais sobre a fé e os próximos passos. "
                "Aqui está o link para se inscrever: https://forms.gle/Cm7d5F9Zv77fgJKDA. "
                "Estamos à disposição para te ajudar nesse caminho!",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Ficamos honrados em receber o seu pedido de oração. "
                "Sinta-se à vontade para compartilhar o que está em seu coração.",
                "Seguem nossos horários de cultos:"
                "🌿 Domingo - Culto da Família - às 19h"
                "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção. "
                "\"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*"
                "🔥 Quinta Fé - Culto dos Milagres - às 20h"
                "Um encontro de fé para vivermos o sobrenatural de Deus. "
                "\"Tudo é possível ao que crê.\" *(Marcos 9:23)*"
                "🎉 Sábado - Culto Alive - às 20h"
                "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*"
                "🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" *(Mateus 18:20)*"
                "Gostaria de mais informações?",
                "Seguem nossos horários de cultos:"
                "🌿 Domingo - Culto da Família - às 19h"
                "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção. "
                "\"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*"
                "🔥 Quinta Fé - Culto dos Milagres - às 20h"
                "Um encontro de fé para vivermos o sobrenatural de Deus. "
                "\"Tudo é possível ao que crê.\" *(Marcos 9:23)*"
                "🎉 Sábado - Culto Alive - às 20h"
                "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*"
                "🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" *(Mateus 18:20)*"
                "Gostaria de mais informações?",
                "Seguem nossos horários de cultos:"
                "🌿 Domingo - Culto da Família - às 19h"
                "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção. "
                "\"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*"
                "🔥 Quinta Fé - Culto dos Milagres - às 20h"
                "Um encontro de fé para vivermos o sobrenatural de Deus. "
                "\"Tudo é possível ao que crê.\" *(Marcos 9:23)*"
                "🎉 Sábado - Culto Alive - às 20h"
                "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
                "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*"
                "🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
                "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" *(Mateus 18:20)*"
                "Gostaria de mais informações?",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "Agradecemos seu contato e esperamos vê-lo em breve!",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "Agradecemos seu contato e esperamos vê-lo em breve!",
                "Aqui está o link para entrar no nosso grupo do WhatsApp: "
                "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK  "
                "Agradecemos seu contato e esperamos vê-lo em breve!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                "Estamos aqui para ouvir e apoiar você!",
                "Paz de Cristo, somos os Homens Corajosos da Mais de Cristo Canasvieiras, "
                "nossa missão é servir a Deus com toda força e coração, nos colocando a frente dos propósitos de Deus, "
                "para sermos, sacerdotes da nossa casa, homens de coragem e temente a Deus."
                "Venha fazer parte deste exército e ficar mais próximo do seu propósito."
                "Segue link do grupo de whatsapp: https://chat.whatsapp.com/H4pFqtsruDr0QJ1NvCMjda  ",
                "Paz de Cristo, somos o Ministério Mulheres Transformadas da Mais de Cristo Canasvieiras. "
                "Nosso objetivo é promover o crescimento espiritual das mulheres, fortalecendo nossa fé e "
                "nos unindo em amor e comunhão. Temos encontros mensais cheios de aprendizado e inspiração."
                "Venha fazer parte deste grupo e viver os propósitos que Deus tem para sua vida."
                "Segue link do grupo de whatsapp: https://chat.whatsapp.com/LT0pN2SPTqf66yt3AWKIAe  ",
                "O Ministério Alive é dedicado aos jovens e adolescentes, com cultos vibrantes e cheios de propósito.",
                "Nossos pastores atuais são:"
                "- Pr Fábio Ferreira"
                "- Pra Cláudia Ferreira"
                "Você pode seguir o Pr Fábio Ferreira no Instagram: @prfabioferreirasoficial"
                "E a Pra Cláudia Ferreira no Instagram: @claudiaferreiras1",
                "Nossos pastores atuais são:"
                "- Pr Fábio Ferreira"
                "- Pra Cláudia Ferreira"
                "Você pode seguir o Pr Fábio Ferreira no Instagram: @prfabioferreirasoficial"
                "E a Pra Cláudia Ferreira no Instagram: @claudiaferreiras1",
                "Olá! Ficamos felizes com seu interesse nos 21 dias de oração. 🙏 "
                "Este evento acontece diariamente, das 23h às 23:30, na igreja, e seguirá até o dia 20 de novembro."
                "Será um tempo especial para buscar paz, inspiração e fortalecer a fé. "
                "Caso precise de mais informações ou queira confirmar presença, estou aqui para ajudar!",
            ]
            logger.info("Usando conjunto de dados de fallback.")

        return perguntas, respostas
    
