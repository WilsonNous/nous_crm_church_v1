# ia_integracao.py - Motor de Busca Inteligente (Sem coluna 'active')
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
        self._cached_responder = lru_cache(maxsize=cache_size)(self._responder_sem_cache)

    def responder_pergunta(self, pergunta_usuario: str = '', contexto: dict = None) -> tuple[str, float]:
        """
        Busca resposta no banco com cache e otimizações.
        Retorna (texto_resposta, confidence).
        """
        if not pergunta_usuario or not pergunta_usuario.strip():
            return "Não entendi sua pergunta. Pode repetir?", 0.0

        pergunta_original = pergunta_usuario.strip()
        pergunta_normalizada = self._normalizar_para_busca(pergunta_usuario)
        
        try:
            return self._cached_responder(pergunta_normalizada, pergunta_original)
        except Exception as e:
            log.error(f"❌ Erro no cache da IA: {e}")
            return self._responder_sem_cache(pergunta_normalizada, pergunta_original)

    def _normalizar_para_busca(self, texto: str) -> str:
        """
        Normaliza texto para busca: lowercase, remove acentos, tokens.
        """
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        tokens = re.findall(r'\b[a-zà-ú0-9]+\b', texto.lower())
        
        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'da', 'do', 
            'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'por', 'para', 'com', 
            'sem', 'sob', 'sobre', 'que', 'se', 'e', 'ou', 'mas', 'sim', 'nao',
            'tambem', 'so', 'só', 'ja', 'já', 'ainda', 'mais', 'menos'
        }
        tokens = [t for t in tokens if t not in stopwords and len(t) >= 2]
        
        return ' '.join(sorted(set(tokens)))

    def _calcular_similaridade(self, texto1: str, texto2: str) -> float:
        """Calcula similaridade entre dois textos."""
        return SequenceMatcher(None, texto1.lower(), texto2.lower()).ratio()

    def _responder_sem_cache(self, pergunta_normalizada: str, pergunta_original: str = None) -> tuple[str, float]:
        """
        Motor de busca inteligente com múltiplas estratégias.
        SEM referência à coluna 'active' (não existe na tabela).
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return self._fallback_response(), 0.3
                
                cursor = conn.cursor()
                tokens = [t for t in pergunta_normalizada.split() if len(t) >= 2]
                
                # ============================================================
                # ESTRATÉGIA 1: BUSCA EXATA (pergunta original)
                # ============================================================
                if pergunta_original:
                    cursor.execute("""
                        SELECT answer FROM knowledge_base
                        WHERE question = %s
                        LIMIT 1
                    """, (pergunta_original,))
                    result = cursor.fetchone()
                    if result:
                        resposta = result[0] if not isinstance(result, dict) else result.get('answer')
                        if resposta:
                            log.info(f"✅ IA: EXATA encontrada")
                            return str(resposta), 1.0

                # ============================================================
                # ESTRATÉGIA 2: KEYWORDS (coluna keywords)
                # ============================================================
                if tokens:
                    keyword_conditions = ' OR '.join(['keywords LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    cursor.execute("""
                        SELECT answer FROM knowledge_base
                        WHERE ({keyword_cond})
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
                        resposta = result[0] if not isinstance(result, dict) else result.get('answer')
                        if resposta:
                            log.info(f"✅ IA: KEYWORDS match ({len(tokens)} tokens)")
                            return str(resposta), 0.95

                # ============================================================
                # ESTRATÉGIA 3: CATEGORIA (mapeamento inteligente)
                # ============================================================
                mapa_categorias = {
                    'horario': 'horarios', 'horarios': 'horarios', 'culto': 'horarios', 'cultos': 'horarios',
                    'programacao': 'horarios', 'agenda': 'horarios', 'evento': 'horarios',
                    'batismo': 'membro', 'membro': 'membro',
                    'pastor': 'pastores', 'pastores': 'pastores', 'lider': 'pastores', 'lideres': 'pastores',
                    'grupo': 'grupos', 'whatsapp': 'grupos', 'gc': 'grupos',
                    'endereco': 'localizacao', 'localizacao': 'localizacao', 'maps': 'localizacao',
                    'oracao': 'oracao', 'oração': 'oracao',
                    'discipulado': 'discipulado',
                    'fundador': 'Fundadores', 'fundadores': 'Fundadores',
                }
                
                for palavra, categoria in mapa_categorias.items():
                    if palavra in pergunta_normalizada:
                        cursor.execute("""
                            SELECT answer FROM knowledge_base
                            WHERE category = %s
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
                            resposta = result[0] if not isinstance(result, dict) else result.get('answer')
                            if resposta:
                                log.info(f"✅ IA: CATEGORIA match ({categoria})")
                                return str(resposta), 0.90

                # ============================================================
                # ESTRATÉGIA 4: LIKE AND (todos os tokens)
                # ============================================================
                if len(tokens) >= 2:
                    like_conditions = ' AND '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    query_like = """
                        SELECT answer FROM knowledge_base
                        WHERE {like_cond}
                        UNION ALL
                        SELECT answer FROM training_pairs
                        WHERE {like_cond}
                        ORDER BY LENGTH(answer) ASC
                        LIMIT 1
                    """.format(like_cond=like_conditions)
                    
                    cursor.execute(query_like, params + params)
                    result = cursor.fetchone()
                    if result:
                        resposta = result[0] if not isinstance(result, dict) else result.get('answer')
                        if resposta:
                            log.info(f"✅ IA: LIKE AND ({len(tokens)} tokens)")
                            return str(resposta), 0.92

                # ============================================================
                # ESTRATÉGIA 5: LIKE OR (pelo menos um token)
                # ============================================================
                if len(tokens) >= 1:
                    like_conditions = ' OR '.join(['question LIKE %s'] * len(tokens))
                    params = [f'%{t}%' for t in tokens]
                    
                    query_like_or = """
                        SELECT answer FROM knowledge_base
                        WHERE ({like_cond})
                        UNION ALL
                        SELECT answer FROM training_pairs
                        WHERE ({like_cond})
                        ORDER BY 
                            CASE 
                                WHEN question LIKE %s THEN 0
                                ELSE 1
                            END,
                            LENGTH(answer) ASC
                        LIMIT 1
                    """.format(like_cond=like_conditions)
                    
                    cursor.execute(query_like_or, params + params + [f'%{tokens[0]}%'])
                    result = cursor.fetchone()
                    if result:
                        resposta = result[0] if not isinstance(result, dict) else result.get('answer')
                        if resposta:
                            log.info(f"✅ IA: LIKE OR ({len(tokens)} tokens)")
                            return str(resposta), 0.85

                # ============================================================
                # ESTRATÉGIA 6: SIMILARIDADE (fallback final)
                # ============================================================
                cursor.execute("""
                    SELECT question, answer FROM knowledge_base
                    ORDER BY id DESC
                    LIMIT 200
                """)
                
                results = cursor.fetchall()
                melhor_resposta = None
                melhor_score = 0.0
                
                for result in results:
                    if isinstance(result, dict):
                        pergunta_db = result.get('question', '')
                        resposta_db = result.get('answer', '')
                    else:
                        pergunta_db = result[0] if len(result) > 0 else ''
                        resposta_db = result[1] if len(result) > 1 else ''
                    
                    similaridade = self._calcular_similaridade(pergunta_original or pergunta_normalizada, pergunta_db)
                    
                    for token in tokens:
                        if token in pergunta_db.lower():
                            similaridade += 0.05
                    
                    if similaridade > melhor_score:
                        melhor_score = similaridade
                        melhor_resposta = resposta_db
                
                if melhor_resposta and melhor_score > 0.25:
                    log.info(f"✅ IA: SIMILARIDADE match (score={melhor_score:.2f})")
                    return str(melhor_resposta), 0.75

                # ============================================================
                # NADA ENCONTRADO
                # ============================================================
                try:
                    cursor.execute("""
                        INSERT INTO unknown_questions (user_id, question, status, created_at)
                        VALUES (%s, %s, %s, NOW())
                    """, ("whatsapp", pergunta_normalizada, "pending"))
                    conn.commit()
                    log.info(f"📝 Pergunta registrada: '{pergunta_normalizada[:60]}...'")
                except Exception as e:
                    log.warning(f"⚠️ Registro pendente: {e}")
                
                return self._fallback_response(), 0.3
                
        except Exception as e:
            log.error(f"❌ Erro IA: {e}", exc_info=True)
            return self._fallback_response(), 0.2

    def _fallback_response(self) -> str:
        return "Ainda não tenho essa resposta, mas já registrei sua pergunta para nosso time. 🙏"

    def limpar_cache(self):
        self._cached_responder.cache_clear()
        log.info("🔄 Cache da IA limpo")

    def get_cache_stats(self) -> dict:
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

def recarregar_cache_ia():
    _get_ia_instance().limpar_cache()

def obter_stats_ia() -> dict:
    return _get_ia_instance().get_cache_stats()
