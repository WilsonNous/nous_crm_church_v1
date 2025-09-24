import logging
import re
import unicodedata
from database import get_db_connection

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

            # Cria um cursor que retorna dicionários (compatível com pymysql)
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
                    resposta = result[0]  # answer está no índice 0
                    intent = result[1]    # category está no índice 1
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
                    resposta = result[0]  # answer
                    intent = result[1]    # category
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
            return {'response': 'Desculpe, ocorreu um erro interno. Tente novamente mais tarde.', 'intent': 'error', 'confidence': 0.0}
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
