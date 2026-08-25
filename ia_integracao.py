# ia_integracao.py - Versão Inteligente com Múltiplas Estratégias de Busca
import logging
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from contextlib import closing
from difflib import SequenceMatcher
from database import get_db_connection
from utilitarios.texto import normalizar_texto

log = logging.getLogger(__name__)

class IAIntegracao:
    def __init__(self, cache_size: int = 512):
        self.cache_size = cache_size
        # Cache LRU para respostas frequentes
        self._cached_responder = lru_cache(maxsize=cache_size)(self._responder_sem_cache)

    def responder_pergunta(self, pergunta_usuario: str = '', contexto: dict = None) -> tuple[str, float]:
        """
        Busca resposta no banco com cache e otimizações.
        Retorna (texto_resposta, confidence).
        """
        if not pergunta_usuario or not pergunta_usuario.strip():
            return "Não entendi sua pergunta. Pode repetir?", 0.0

        # Guarda a pergunta original
        pergunta_original = pergunta_usuario.strip()
        
        # Normaliza a pergunta para cache e busca
        pergunta_normalizada = self._normalizar_para_busca(pergunta_usuario)
        
        # Tenta cache primeiro
        try:
            return self._cached_responder(pergunta_normalizada, pergunta_original)
        except Exception as e:
            log.error(f"❌ Erro no cache da IA: {e}")
            return self._responder_sem_cache(pergunta_normalizada, pergunta_original)

    def _normalizar_para_busca(self, texto: str) -> str:
        """
        Normaliza texto para busca com múltiplas variações.
        """
        # Remove acentos
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        
        # Lowercase e extrai palavras
        tokens = re.findall(r'\b[a-zà-ú0-9]+\b', texto.lower())
        
        # Stopwords reduzidas (mantém palavras importantes)
        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'da', 'do', 
            'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 
            'sem', 'sob', 'sobre', 'que', 'qual', 'quais', 'quem', 'como', 
            'quando', 'onde', 'entao', 'mas', 'e', 'ou', 'se', 'nao', 'não', 
            'sim', 'ja', 'já', 'ainda', 'tambem', 'também', 'so', 'só', 
            'somente', 'apenas', 'mais', 'menos', 'muito', 'pouco'
        }
        tokens = [t for t in tokens if t not in stopwords]
        
        # Retorna tokens únicos
        return ' '.join(sorted(set(tokens)))

    def _calcular_similaridade(self, texto1: str, texto2: str) -> float:
        """
        Calcula similaridade entre dois textos usando SequenceMatcher.
        """
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio()

    def _responder_sem_cache(self, pergunta_normalizada: str, pergunta_original: str = None) -> tuple[str, float]:
        """
        Lógica de busca inteligente com múltiplas estratégias.
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return self._fallback_response(), 0.3
                
                cursor = conn.cursor()
                
                # ============================================================
                # ESTRATÉGIA 1: BUSCA EXATA (mais precisa)
                # ============================================================
                if pergunta_original:
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
                        else:
                            resposta = result[0] if len(result) > 0 else None
                        
                        if resposta:
                            log.info(f"✅ IA: BUSCA EXATA encontrada")
                            return str(resposta), 1.0

                # ============================================================
                # ESTRATÉGIA 2: BUSCA POR KEYWORDS (prioridade máxima)
                # ============================================================
                # Busca por palavras-chave na coluna keywords
                tokens = [t for t in pergunta_normalizada.split() if len(t) >= 2]
                
                if tokens:
                    # Constrói condições para keywords
                    keyword_conditions = ' OR '.join(['keywords LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    cursor.execute("""
                        SELECT answer, 'kb' as fonte
                        FROM knowledge_base
                        WHERE ({keyword_cond}) AND active = 1
                        ORDER BY 
                            CASE 
                                WHEN keywords LIKE %s THEN 0
                                WHEN keywords LIKE %s THEN 1
                                ELSE 2
                            END,
                            id DESC
                        LIMIT 1
                    """.format(keyword_cond=keyword_conditions), 
                    params + [f'%{tokens[0]}%', f'%{" ".join(tokens[:2])}%'])
                    
                    result = cursor.fetchone()
                    if result:
                        if isinstance(result, dict):
                            resposta = result.get('answer')
                        else:
                            resposta = result[0] if len(result) > 0 else None
                        
                        if resposta:
                            log.info(f"✅ IA: KEYWORDS match com {len(tokens)} tokens")
                            return str(resposta), 0.95

                # ============================================================
                # ESTRATÉGIA 3: BUSCA POR CATEGORIA + KEYWORDS
                # ============================================================
                # Mapeamento de palavras para categorias
                mapa_categorias = {
                    'horario': 'horarios',
                    'horarios': 'horarios',
                    'culto': 'horarios',
                    'cultos': 'horarios',
                    'programacao': 'horarios',
                    'agenda': 'horarios',
                    'evento': 'horarios',
                    'batismo': 'membro',
                    'membro': 'membro',
                    'pastor': 'pastores',
                    'pastores': 'pastores',
                    'lider': 'pastores',
                    'lideres': 'pastores',
                    'grupo': 'grupos',
                    'whatsapp': 'grupos',
                    'gc': 'grupos',
                    'endereco': 'localizacao',
                    'localizacao': 'localizacao',
                    'maps': 'localizacao',
                    'oracao': 'oracao',
                    'oração': 'oracao',
                    'discipulado': 'discipulado',
                    'fundador': 'Fundadores',
                    'fundadores': 'Fundadores',
                }
                
                # Encontra a categoria mais relevante
                for palavra, categoria in mapa_categorias.items():
                    if palavra in pergunta_normalizada:
                        # Busca por categoria e palavras-chave
                        cursor.execute("""
                            SELECT answer, question, category
                            FROM knowledge_base
                            WHERE category = %s AND active = 1
                            ORDER BY 
                                CASE 
                                    WHEN question LIKE %s THEN 0
                                    WHEN keywords LIKE %s THEN 1
                                    ELSE 2
                                END,
                                id DESC
                            LIMIT 1
                        """, (categoria, f'%{palavra}%', f'%{palavra}%'))
                        
                        result = cursor.fetchone()
                        if result:
                            if isinstance(result, dict):
                                resposta = result.get('answer')
                            else:
                                resposta = result[0] if len(result) > 0 else None
                            
                            if resposta:
                                log.info(f"✅ IA: CATEGORIA match '{categoria}' (palavra: {palavra})")
                                return str(resposta), 0.90

                # ============================================================
                # ESTRATÉGIA 4: LIKE AND (múltiplos tokens)
                # ============================================================
                if len(tokens) >= 2:
                    like_conditions = ' AND '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    query_like = """
                        SELECT answer, 'kb' as fonte FROM knowledge_base
                        WHERE {like_cond} AND active = 1
                        UNION ALL
                        SELECT answer, 'train' as fonte FROM training_pairs
                        WHERE {like_cond} AND active = 1
                        ORDER BY 
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END,
                            LENGTH(answer) ASC
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
                            confidence = 0.92 if fonte == 'kb' else 0.85
                            log.info(f"✅ IA: LIKE AND match com {len(tokens)} tokens")
                            return str(resposta), confidence

                # ============================================================
                # ESTRATÉGIA 5: LIKE OR (mais flexível)
                # ============================================================
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
                            CASE WHEN fonte = 'kb' THEN 0 ELSE 1 END,
                            LENGTH(answer) ASC
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
                            confidence = 0.85 if fonte == 'kb' else 0.78
                            log.info(f"✅ IA: LIKE OR match com {len(tokens)} tokens")
                            return str(resposta), confidence

                # ============================================================
                # ESTRATÉGIA 6: FULLTEXT MATCH (busca semântica)
                # ============================================================
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
                            
                            if resposta and similarity > 0.3:
                                confidence = 0.95 if fonte == 'kb' else 0.90
                                log.info(f"✅ IA: FULLTEXT match (similaridade={similarity:.2f})")
                                return str(resposta), confidence
                                
                except Exception as e:
                    log.debug(f"⚠️ FULLTEXT não disponível: {e}")

                # ============================================================
                # ESTRATÉGIA 7: BUSCA POR SIMILARIDADE (fallback final)
                # ============================================================
                # Busca todas as perguntas e calcula similaridade
                cursor.execute("""
                    SELECT question, answer, category
                    FROM knowledge_base
                    WHERE active = 1
                    ORDER BY id DESC
                    LIMIT 100
                """)
                
                results = cursor.fetchall()
                melhor_match = None
                melhor_similaridade = 0.0
                
                for result in results:
                    if isinstance(result, dict):
                        pergunta_db = result.get('question', '')
                        resposta_db = result.get('answer', '')
                    else:
                        pergunta_db = result[0] if len(result) > 0 else ''
                        resposta_db = result[1] if len(result) > 1 else ''
                    
                    # Calcula similaridade com a pergunta normalizada
                    similaridade = self._calcular_similaridade(pergunta_normalizada, pergunta_db)
                    
                    # Também verifica se algum token importante está presente
                    for token in tokens:
                        if token in pergunta_db.lower():
                            similaridade += 0.1
                    
                    if similaridade > melhor_similaridade:
                        melhor_similaridade = similaridade
                        melhor_match = resposta_db
                
                if melhor_match and melhor_similaridade > 0.3:
                    log.info(f"✅ IA: SIMILARIDADE match (score={melhor_similaridade:.2f})")
                    return str(melhor_match), 0.75

                # ============================================================
                # NADA ENCONTRADO - Registra para treinamento
                # ============================================================
                try:
                    cursor.execute("""
                        INSERT INTO unknown_questions (user_id, question, status, created_at)
                        VALUES (%s, %s, %s, NOW())
                    """, ("whatsapp", pergunta_normalizada, "pending"))
                    conn.commit()
                    log.info(f"📝 Pergunta registrada para treino: '{pergunta_normalizada[:60]}...'")
                except Exception as e:
                    log.warning(f"⚠️ Não foi possível registrar pergunta pendente: {e}")
                
                return self._fallback_response(), 0.3
                
        except Exception as e:
            log.error(f"❌ Erro na busca da IA: {e}", exc_info=True)
            return self._fallback_response(), 0.2

    def _fallback_response(self) -> str:
        """Resposta padrão quando nada é encontrado."""
        return "Ainda não tenho essa resposta, mas já registrei sua pergunta para nosso time. 🙏"

    def limpar_cache(self):
        """Limpa o cache LRU."""
        self._cached_responder.cache_clear()
        log.info("🔄 Cache da IA limpo")

    def get_cache_stats(self) -> dict:
        """Retorna estatísticas do cache."""
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
# Funções auxiliares
# =======================

_ia_instance = None

def _get_ia_instance() -> IAIntegracao:
    global _ia_instance
    if _ia_instance is None:
        _ia_instance = IAIntegracao()
    return _ia_instance

def gerar_resposta(prompt: str, contexto: dict = None) -> dict:
    ia = _get_ia_instance()
    texto, conf = ia.responder_pergunta(prompt, contexto)
    return {'texto': texto, 'meta': {'confidence': conf}}

def consulta_ia(prompt: str, *args, **kwargs) -> dict:
    return gerar_resposta(prompt, *args, **kwargs)

def call_ai(prompt: str, *args, **kwargs) -> dict:
    return gerar_resposta(prompt, *args, **kwargs)

IS_MOCK = False


# =======================
# Utilitários para admin
# =======================

def recarregar_cache_ia():
    _get_ia_instance().limpar_cache()

def obter_stats_ia() -> dict:
    return _get_ia_instance().get_cache_stats()
