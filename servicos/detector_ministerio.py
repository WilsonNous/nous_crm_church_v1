from constantes import palavras_chave_ministerios
from utilitarios.texto import normalizar_texto

def detectar_palavra_chave_ministerio(texto_recebido: str):
    """
    Detecta se o texto contém palavras-chave relacionadas a ministérios
    (ex: 'louvor', 'jovens', 'intercessão', etc.).
    Retorna a mensagem correspondente se houver.
    """
    if not texto_recebido:
        return None

    texto_recebido = normalizar_texto(texto_recebido).replace('ç', 'c')
    for palavra, resposta in palavras_chave_ministerios.items():
        if palavra in texto_recebido or palavra.rstrip('s') in texto_recebido:
            return resposta
    return None
