# ia_integracao.py - Integração com banco de dados (CORRIGIDA)
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

        # Guarda a pergunta original para busca
        pergunta_original = pergunta_usuario.strip()
        
        # Normaliza a pergunta para cache e busca
        pergunta_normalizada = self._normalizar_para_busca(pergunta_usuario)
        
        # Tenta cache primeiro (muito mais rápido)
        try:
            # Passa a pergunta original no contexto
            return self._cached_responder(pergunta_normalizada, pergunta_original)
        except Exception as e:
            log.error(f"❌ Erro no cache da IA: {e}")
            return self._responder_sem_cache(pergunta_normalizada, pergunta_original)

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

    def _responder_sem_cache(self, pergunta_normalizada: str, pergunta_original: str = None) -> tuple[str, float]:
        """
        Lógica real de busca no banco (sem cache).
        ESTRATÉGIA: LIKE AND → LIKE OR → FULLTEXT → Categoria
        Retorna (resposta, confidence).
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return self._fallback_response(), 0.3
                
                cursor = conn.cursor()
                
                # 🔍 ESTRATÉGIA 0: Busca por pergunta original (mais importante!)
                if pergunta_original:
                    try:
                        # Busca exata na knowledge_base
                        cursor.execute("""
                            SELECT answer, 'kb' as fonte
                            FROM knowledge_base
                            WHERE question = %s AND active = 1
                            LIMIT 1
                        """, (pergunta_original,))
                        result = cursor.fetchone()
                        
                        if result:
                            if isinstance(result, dict):
                                resposta = result.get('answer')
                                fonte = result.get('fonte')
                            else:
                                resposta = result[0] if len(result) > 0 else None
                                fonte = result[1] if len(result) > 1 else 'kb'
                            
                            if resposta:
                                log.info(f"✅ IA: busca EXATA encontrada (fonte={fonte})")
                                return str(resposta), 0.98
                    except Exception as e:
                        log.debug(f"⚠️ Busca EXATA falhou: {e}")
                
                # 🔍 ESTRATÉGIA 1: LIKE com tokens (AND lógico) - PRIORIDADE MÁXIMA
                tokens = [t for t in pergunta_normalizada.split() if len(t) >= 2]
                
                if len(tokens) >= 2:
                    # Constrói a query com placeholders %s para os tokens
                    like_conditions = ' AND '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    # Busca na knowledge_base primeiro (prioridade)
                    query_like = """
                        SELECT answer, 'kb' as fonte FROM knowledge_base
                        WHERE {like_cond} AND active = 1
                        UNION ALL
                        SELECT answer, 'train' as fonte FROM training_pairs
                        WHERE {like_cond} AND active = 1
                        ORDER BY 
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END
                        LIMIT 1
                    """.format(like_cond=like_conditions)
                    
                    cursor.execute(query_like, params + params)
                    result = cursor.fetchone()
                    
                    if result:
                        if isinstance(result, dict):
                            resposta = result.get('answer')
                            fonte = result.get('fonte')
                        else:
                            resposta = result[0] if len(result) > 0 else None
                            fonte = result[1] if len(result) > 1 else 'train'
                        
                        if resposta:
                            confidence = 0.95 if fonte == 'kb' else 0.85
                            log.info(f"✅ IA: LIKE AND match com {len(tokens)} tokens (fonte={fonte})")
                            return str(resposta), confidence
                
                # 🔍 ESTRATÉGIA 2: LIKE com OR (mais flexível)
                if len(tokens) >= 1:
                    like_conditions = ' OR '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    query_like_or = """
                        SELECT answer, 'kb' as fonte FROM knowledge_base
                        WHERE ({like_cond}) AND active = 1
                        UNION ALL
                        SELECT answer, 'train' as fonte FROM training_pairs
                        WHERE ({like_cond}) AND active = 1
                        ORDER BY 
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END
                        LIMIT 1
                    """.format(like_cond=like_conditions)
                    
                    cursor.execute(query_like_or, params + params)
                    result = cursor.fetchone()
                    
                    if result:
                        if isinstance(result, dict):
                            resposta = result.get('answer')
                            fonte = result.get('fonte')
                        else:
                            resposta = result[0] if len(result) > 0 else None
                            fonte = result[1] if len(result) > 1 else 'train'
                        
                        if resposta:
                            confidence = 0.90 if fonte == 'kb' else 0.80
                            log.info(f"✅ IA: LIKE OR match com {len(tokens)} tokens (fonte={fonte})")
                            return str(resposta), confidence
                
                # 🔍 ESTRATÉGIA 3: FULLTEXT MATCH
                try:
                    search_term = re.sub(r'[^\w\s]', '', pergunta_normalizada).strip()
                    
                    if len(search_term) >= 3:
                        query_fulltext = """
                            SELECT kb.answer, 'kb' as fonte,
                                   MATCH(kb.question, kb.answer) AGAINST(%s IN NATURAL LANGUAGE MODE) as similarity
                            FROM knowledge_base kb
                            WHERE MATCH(kb.question, kb.answer) AGAINST(%s IN NATURAL LANGUAGE MODE) AND kb.active = 1
                            
                            UNION ALL
                            
                            SELECT tp.answer, 'train' as fonte,
                                   MATCH(tp.question, tp.answer) AGAINST(%s IN NATURAL LANGUAGE MODE) as similarity
                            FROM training_pairs tp
                            WHERE MATCH(tp.question, tp.answer) AGAINST(%s IN NATURAL LANGUAGE MODE) AND tp.active = 1
                            
                            ORDER BY 
                                CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END,
                                similarity DESC
                            LIMIT 1
                        """
                        cursor.execute(query_fulltext, (search_term, search_term, search_term, search_term))
                        result = cursor.fetchone()
                        
                        if result:
                            if isinstance(result, dict):
                                resposta = result.get('answer')
                                fonte = result.get('fonte')
                                similarity = result.get('similarity', 0) or 0
                            else:
                                resposta = result[0] if len(result) > 0 else None
                                fonte = result[1] if len(result) > 1 else 'train'
                                similarity = result[2] if len(result) > 2 else 0
                            
                            if resposta and similarity > 0.5:
                                confidence = 0.98 if fonte == 'kb' else 0.95
                                log.info(f"✅ IA: FULLTEXT match (similaridade={similarity:.2f}, fonte={fonte})")
                                return str(resposta), confidence
                                
                except Exception as e:
                    log.debug(f"⚠️ FULLTEXT não disponível: {e}")
                
                # 🔍 ESTRATÉGIA 4: Busca por categoria
                categorias_conhecidas = {
                    'horario': 'horarios',
                    'culto': 'horarios',
                    'horarios': 'horarios',
                    'programacao': 'horarios',
                    'agenda': 'horarios',
                    'evento': 'horarios',
                    'batismo': 'membro',
                    'membro': 'membro',
                    'pastor': 'pastores',
                    'lider': 'pastores',
                    'grupo': 'grupos',
                    'whatsapp': 'grupos',
                    'gc': 'grupos',
                    'endereco': 'localizacao',
                    'localizacao': 'localizacao',
                    'maps': 'localizacao',
                    'oracao': 'oracao',
                }
                
                for palavra, categoria in categorias_conhecidas.items():
                    if palavra in pergunta_normalizada:
                        cursor.execute("""
                            SELECT answer FROM knowledge_base 
                            WHERE category = %s AND active = 1
                            ORDER BY id DESC
                            LIMIT 1
                        """, (categoria,))
                        result = cursor.fetchone()
                        if result:
                            if isinstance(result, dict):
                                resposta = result.get('answer')
                            else:
                                resposta = result[0] if result else None
                            
                            if resposta:
                                log.info(f"✅ IA: resposta por categoria '{categoria}' (palavra: {palavra})")
                                return str(resposta), 0.80
                
                # ❌ Nada encontrado: registra para treinamento futuro
                try:
                    cursor.execute("""
                        INSERT INTO unknown_questions (user_id, question, status, created_at)
                        VALUES (%s, %s, %s, NOW())
                    """, ("whatsapp", pergunta_normalizada, "pending"))
                    conn.commit()
                    log.info(f"📝 Pergunta registrada para treino: '{pergunta_normalizada[:60]}...'")
                except Exception as e:
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
