# ia_integracao.py - Integração real com banco de dados (CORRIGIDA + VALIDADA)
import logging
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from contextlib import closing
from database import get_db_connection
from utilitarios.texto import normalizar_texto

log = logging.getLogger(__name__)

class IAIntegracao:
    def __init__(self, cache_size: int = 256):
        self.cache_size = cache_size
        # Cache LRU para respostas frequentes (thread-safe)
        self._cached_responder = lru_cache(maxsize=cache_size)(self._responder_sem_cache)

    def responder_pergunta(self, pergunta_usuario: str = '', contexto: dict = None) -> tuple[str, float]:
        """
        Busca resposta no banco com cache e otimizações.
        Retorna (texto_resposta, confidence).
        """
        if not pergunta_usuario or not pergunta_usuario.strip():
            return "Não entendi sua pergunta. Pode repetir?", 0.0

        # Normaliza a pergunta para cache e busca
        pergunta_normalizada = self._normalizar_para_busca(pergunta_usuario)
        
        # Tenta cache primeiro (muito mais rápido)
        try:
            return self._cached_responder(pergunta_normalizada)
        except Exception as e:
            log.error(f"❌ Erro no cache da IA: {e}")
            return self._responder_sem_cache(pergunta_normalizada)

    def _normalizar_para_busca(self, texto: str) -> str:
        """
        Normaliza texto para busca: lowercase, remove acentos, tokens únicos.
        Ex: "Quais horários temos cultos?" → "quais horario temos culto"
        """
        # Remove acentos
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        
        # Lowercase e extrai apenas palavras
        tokens = re.findall(r'\b[a-zà-ú0-9]+\b', texto.lower())
        
        # Remove stopwords comuns em português
        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'da', 'do', 
            'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 
            'sem', 'sob', 'sobre', 'que', 'qual', 'quais', 'quem', 'como', 
            'quando', 'onde', 'por que', 'porque', 'entao', 'mas', 'e', 'ou', 
            'se', 'nao', 'não', 'sim', 'ja', 'já', 'ainda', 'tambem', 'também', 
            'so', 'só', 'somente', 'apenas', 'mais', 'menos', 'muito', 'pouco', 
            'tudo', 'nada', 'algo', 'alguem', 'ninguem', 'todo', 'toda', 'todos', 
            'todas', 'este', 'esta', 'estes', 'estas', 'esse', 'essa', 'esses', 
            'essas', 'aquele', 'aquela', 'aqueles', 'aquelas', 'isto', 'isso', 'aquilo'
        }
        tokens = [t for t in tokens if t not in stopwords]
        
        # Junta tokens únicos (ordem não importa para busca)
        return ' '.join(sorted(set(tokens)))

    def _responder_sem_cache(self, pergunta_normalizada: str) -> tuple[str, float]:
        """
        Lógica real de busca no banco (sem cache).
        Retorna (resposta, confidence).
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return self._fallback_response(), 0.3
                
                cursor = conn.cursor()
                
                # 🔍 ESTRATÉGIA 1: Match por tokens (AND lógico)
                tokens = pergunta_normalizada.split()
                
                if len(tokens) >= 2:
                    # Constrói condições LIKE com placeholders %s
                    like_conditions = ' AND '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    # ✅ CORREÇÃO: Usar .format() para estrutura da query, NÃO f-string
                    # Isso evita conflito entre %s (placeholders) e formatação de string
                    query = """
                        SELECT answer, 'kb' as fonte FROM knowledge_base
                        WHERE {}
                        UNION ALL
                        SELECT answer, 'train' as fonte FROM training_pairs
                        WHERE {}
                        ORDER BY 
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END,
                            updated_at DESC
                        LIMIT 1
                    """.format(like_conditions, like_conditions)
                    
                    cursor.execute(query, params)
                    
                else:
                    # Fallback para perguntas curtas (1 token ou vazio)
                    query = """
                        SELECT answer, 'kb' as fonte FROM knowledge_base
                        WHERE question LIKE %s
                        UNION ALL
                        SELECT answer, 'train' as fonte FROM training_pairs
                        WHERE question LIKE %s
                        ORDER BY 
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END,
                            updated_at DESC
                        LIMIT 1
                    """
                    cursor.execute(query, (f'%{pergunta_normalizada}%', f'%{pergunta_normalizada}%'))
                
                # ✅ VALIDAÇÃO: Extrair resultado de forma segura (DictCursor ou lista)
                result = cursor.fetchone()
                if result:
                    # Suporta tanto DictCursor quanto tuple
                    if isinstance(result, dict):
                        resposta = result.get('answer')
                        fonte = result.get('fonte')
                    else:
                        # Resultado como tuple: (answer, fonte)
                        resposta = result[0] if len(result) > 0 else None
                        fonte = result[1] if len(result) > 1 else 'train'
                    
                    if resposta:
                        confidence = 0.95 if fonte == 'kb' else 0.90
                        log.debug(f"✅ IA: resposta encontrada (fonte={fonte}, conf={confidence})")
                        return str(resposta), confidence
                
                # 🔍 ESTRATÉGIA 2: Busca por categoria (fallback)
                categorias_conhecidas = [
                    'horarios', 'culto', 'batismo', 'membro', 'oracao', 
                    'grupo', 'whatsapp', 'discipulado', 'novo come', 
                    'pastor', 'lider', 'evento'
                ]
                
                for cat in categorias_conhecidas:
                    if cat in pergunta_normalizada:
                        cursor.execute("""
                            SELECT answer FROM knowledge_base 
                            WHERE category = %s 
                            ORDER BY updated_at DESC LIMIT 1
                        """, (cat,))
                        result = cursor.fetchone()
                        if result:
                            # Extrair resposta de forma segura
                            if isinstance(result, dict):
                                resposta = result.get('answer')
                            else:
                                resposta = result[0] if result else None
                            
                            if resposta:
                                log.debug(f"✅ IA: resposta por categoria '{cat}'")
                                return str(resposta), 0.85
                
                # ❌ Nada encontrado: registra para treinamento futuro
                try:
                    cursor.execute("""
                        INSERT INTO unknown_questions (user_id, question, status, created_at)
                        VALUES (%s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE status = VALUES(status), updated_at = NOW()
                    """, ("whatsapp", pergunta_normalizada, "pending"))
                    conn.commit()
                    log.info(f"📝 Pergunta registrada para treino: '{pergunta_normalizada[:60]}...'")
                except Exception as e:
                    # Não falhar se não conseguir registrar pendência
                    log.warning(f"⚠️ Não foi possível registrar pergunta pendente: {e}")
                
                return self._fallback_response(), 0.5
                
        except Exception as e:
            log.error(f"❌ Erro na busca da IA: {e}", exc_info=True)
            return self._fallback_response(), 0.2

    def _fallback_response(self) -> str:
        """Resposta padrão quando nada é encontrado."""
        return "Ainda não tenho essa resposta, mas já registrei sua pergunta para nosso time. 🙏"

    def limpar_cache(self):
        """Limpa o cache LRU (útil após novo treinamento)."""
        self._cached_responder.cache_clear()
        log.info("🔄 Cache da IA limpo")

    def get_cache_stats(self) -> dict:
        """Retorna estatísticas do cache para monitoramento."""
        cache_info = self._cached_responder.cache_info()
        total = cache_info.hits + cache_info.misses
        return {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "size": cache_info.currsize,
            "maxsize": cache_info.maxsize,
            "hit_rate": round(cache_info.hits / max(total, 1) * 100, 1)
        }


# =======================
# Funções auxiliares (compatibilidade com código legado)
# =======================

_ia_instance = None

def _get_ia_instance() -> IAIntegracao:
    """Singleton para evitar recriar cache a cada chamada."""
    global _ia_instance
    if _ia_instance is None:
        _ia_instance = IAIntegracao()
    return _ia_instance

def gerar_resposta(prompt: str, contexto: dict = None) -> dict:
    """Compatível com código legado: retorna dict com texto e meta."""
    ia = _get_ia_instance()
    texto, conf = ia.responder_pergunta(prompt, contexto)
    return {'texto': texto, 'meta': {'confidence': conf}}

def consulta_ia(prompt: str, *args, **kwargs) -> dict:
    """Alias para gerar_resposta (compatibilidade)."""
    return gerar_resposta(prompt, *args, **kwargs)

def call_ai(prompt: str, *args, **kwargs) -> dict:
    """Alias para gerar_resposta (compatibilidade)."""
    return gerar_resposta(prompt, *args, **kwargs)

# Flag de compatibilidade
IS_MOCK = False


# =======================
# Utilitários para admin (opcional)
# =======================

def recarregar_cache_ia():
    """Chamada manual para limpar cache após novo treinamento."""
    _get_ia_instance().limpar_cache()

def obter_stats_ia() -> dict:
    """Retorna stats da IA para dashboard admin."""
    return _get_ia_instance().get_cache_stats()
