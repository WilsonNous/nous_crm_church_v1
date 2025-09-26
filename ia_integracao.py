# ia_integracao.py - Integração real com banco de dados
import logging
from datetime import datetime
from database import get_db_connection

class IAIntegracao:
    def __init__(self):
        self.mock = False  # agora não é mais mock

    def responder_pergunta(self, pergunta_usuario='', contexto=None):
        """
        Busca resposta no banco. Se não existir, registra a pergunta como pendente.
        Retorna (texto_resposta, confidence).
        """
        if not pergunta_usuario:
            return "Não entendi sua pergunta. Pode repetir?", 0.0

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 1. Procura em knowledge_base
            cursor.execute("""
                SELECT answer FROM knowledge_base
                WHERE question LIKE %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (f"%{pergunta_usuario}%",))
            result = cursor.fetchone()
            if result:
                resposta = result.get('answer') if isinstance(result, dict) else result[0]
                return resposta, 0.95

            # 2. Procura em training_pairs
            cursor.execute("""
                SELECT answer FROM training_pairs
                WHERE question LIKE %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (f"%{pergunta_usuario}%",))
            result = cursor.fetchone()
            if result:
                resposta = result.get('answer') if isinstance(result, dict) else result[0]
                return resposta, 0.90

            # 3. Se não encontrou, registra em unknown_questions
            cursor.execute("""
                INSERT INTO unknown_questions (user_id, question, status, created_at)
                VALUES (%s, %s, %s, %s)
            """, ("whatsapp", pergunta_usuario, "pending", datetime.now()))
            conn.commit()

            return (
                "Ainda não tenho essa resposta, mas já registrei sua pergunta para nosso time. 🙏",
                0.5
            )

        except Exception as e:
            logging.error(f"Erro no IAIntegracao: {e}")
            return "[ERRO] Não consegui processar sua pergunta.", 0.0
        finally:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

# Funções auxiliares compatíveis com código legado
def gerar_resposta(prompt, contexto=None):
    ia = IAIntegracao()
    texto, conf = ia.responder_pergunta(prompt, contexto)
    return {'texto': texto, 'meta': {'confidence': conf}}

def consulta_ia(prompt, *args, **kwargs):
    return gerar_resposta(prompt)

def call_ai(prompt, *args, **kwargs):
    return gerar_resposta(prompt)

# Flag de compatibilidade
IS_MOCK = False
