import unicodedata
from constantes import palavras_chave_ministerios

def normalizar_texto(texto: str) -> str:
    """
    Remove acentos, coloca em minúsculo e tira espaços extras.
    """
    texto = texto.strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

def detectar_palavra_chave_ministerio(texto_recebido: str):
    """
    Detecta se a mensagem contém alguma palavra-chave ligada a ministérios.
    """
    texto_recebido = normalizar_texto(texto_recebido).replace('ç', 'c')
    for palavra, resposta in palavras_chave_ministerios.items():
        if palavra in texto_recebido or palavra.rstrip('s') in texto_recebido:
            return resposta
    return None

def detectar_saudacao(texto: str) -> bool:
    """
    Verifica se o texto contém uma saudação típica.
    """
    saudacoes = [
        "ola", "oi", "bom dia", "boa tarde", "boa noite", "eae", "e aí",
        "saudacoes", "a paz do senhor", "a paz de cristo", "paz"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(saudacao in texto_normalizado for saudacao in saudacoes)

def detectar_agradecimento(texto: str) -> bool:
    """
    Verifica se a mensagem é de agradecimento.
    """
    palavras_agradecimento = [
        "obrigado", "obrigada", "grato", "grata",
        "agradecido", "agradecida", "muito obrigado", "muito obrigada",
        "amem", "amém", "aleluia", "gloria a deus"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(palavra in texto_normalizado for palavra in palavras_agradecimento)

