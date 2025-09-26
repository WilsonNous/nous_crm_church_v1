# ia_integracao.py - SAFE MOCK implementation
# This mock avoids external API calls and provides deterministic responses for local testing.
import os
import logging
def gerar_resposta(prompt, contexto=None):
    """Simula uma integração com IA.
    Retorna um dicionário com 'texto' e 'meta' para compatibilidade com o código existente.
    """
    logging.info("[ia_integracao.mock] gerar_resposta called with prompt len=%d", len(prompt) if prompt else 0)
    # Simple echo with a short transformation
    texto = f"[MOCK IA] Recebido prompt: {prompt[:200]}"
    meta = {'mock': True, 'timestamp': os.getenv('MOCK_TIME', 'now')}
    return {'texto': texto, 'meta': meta}

# For compatibility: older code might call `consulta_ia` or `call_ai`
def consulta_ia(*args, **kwargs):
    return gerar_resposta(args[0] if args else kwargs.get('prompt', ''))

def call_ai(*args, **kwargs):
    return gerar_resposta(args[0] if args else kwargs.get('prompt', ''))

# Provide a flag so routes can detect mock mode
IS_MOCK = True


class IAIntegracao:
    def __init__(self, *args, **kwargs):
        self.mock = True

    def responder_pergunta(self, pergunta_usuario='', contexto=None):
        # Return (resposta_texto, confidence)
        resp = gerar_resposta(pergunta_usuario, contexto)
        texto = resp.get('texto') if isinstance(resp, dict) else str(resp)
        # mock confidence: 0.9 for non-empty, else 0.0
        conf = 0.9 if texto else 0.0
        return texto, conf
