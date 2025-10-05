import unicodedata
import re
import logging

def normalizar_texto(texto: str) -> str:
    """
    Remove acentos, converte para minúsculas e elimina espaços extras.
    """
    if not texto:
        return ""
    texto = texto.strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'\s+', ' ', texto)  # remove espaços duplos
    return texto


def detectar_saudacao(texto: str) -> bool:
    """
    Retorna True se o texto contiver alguma saudação comum.
    """
    if not texto:
        return False
    texto = normalizar_texto(texto)
    saudacoes = [
        "ola", "oi", "bom dia", "boa tarde", "boa noite",
        "eae", "e ai", "a paz", "paz de cristo", "paz do senhor"
    ]
    return any(s in texto for s in saudacoes)


def detectar_agradecimento(texto: str) -> bool:
    """
    Retorna True se o texto contiver palavras de agradecimento.
    """
    if not texto:
        return False
    texto = normalizar_texto(texto)
    palavras = [
        "obrigado", "obrigada", "grato", "grata", "agradecido",
        "agradecida", "amem", "amem", "amém", "aleluia", "gloria a deus"
    ]
    return any(p in texto for p in palavras)


def validar_data_nascimento(data: str) -> bool:
    """
    Valida se a data está no formato DD/MM/AAAA.
    """
    if not data:
        return False
    padrao = r"^\d{2}/\d{2}/\d{4}$"
    valido = bool(re.match(padrao, data))
    if not valido:
        logging.warning(f"⚠️ Data de nascimento inválida: {data}")
    return valido
