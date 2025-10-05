def obter_primeiro_nome(nome_completo: str) -> str:
    """
    Retorna o primeiro nome de um nome completo.
    """
    if not nome_completo:
        return "Visitante"
    partes = nome_completo.strip().split()
    return partes[0].capitalize() if partes else "Visitante"


def normalizar_telefone(numero: str) -> str:
    """
    Remove o prefixo do país (55) e caracteres não numéricos.
    Retorna o número no formato nacional.
    """
    if not numero:
        return ""
    numero = ''.join(filter(str.isdigit, numero))
    if numero.startswith("55"):
        numero = numero[2:]
    return numero
