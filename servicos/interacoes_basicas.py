import logging
import unicodedata
from database import salvar_conversa, atualizar_status
from servicos.fila_mensagens import adicionar_na_fila
from constantes import EstadoVisitante, palavras_chave_ministerios

# ------------------------
# Utilitários de texto
# ------------------------
def normalizar_texto(texto: str) -> str:
    texto = texto.strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

# ------------------------
# Detectores
# ------------------------
def detectar_saudacao(texto: str) -> bool:
    saudacoes = [
        "ola", "oi", "bom dia", "boa tarde", "boa noite", "eae", "e aí",
        "saudacoes", "a paz do senhor", "a paz de cristo", "paz"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(s in texto_normalizado for s in saudacoes)


def detectar_agradecimento(texto: str) -> bool:
    palavras_agradecimento = [
        "obrigado", "obrigada", "grato", "grata", "agradecido", "agradecida",
        "muito obrigado", "muito obrigada", "amem", "amém", "aleluia", "gloria a deus"
    ]
    texto_normalizado = normalizar_texto(texto)
    return any(p in texto_normalizado for p in palavras_agradecimento)


def detectar_palavra_chave_ministerio(texto_recebido: str):
    """
    Detecta se a mensagem contém alguma palavra-chave ligada a ministérios.
    Retorna a resposta configurada em 'constantes.palavras_chave_ministerios'.
    """
    texto_recebido = normalizar_texto(texto_recebido).replace('ç', 'c')
    for palavra, resposta in palavras_chave_ministerios.items():
        if palavra in texto_recebido or palavra.rstrip('s') in texto_recebido:
            return resposta
    return None

# ------------------------
# Processadores
# ------------------------
def processar_saudacao(numero: str, nome_visitante: str, message_sid: str, origem: str = "integra+"):
    """Responde a uma saudação inicial"""
    resposta = f"""Olá, {nome_visitante}! 😊
Sou o **Integra+**, assistente do Ministério de Integração da MAIS DE CRISTO Canasvieiras.

Como posso te ajudar hoje?

👉 *Aqui, o batismo é o batismo nas águas por imersão, como uma decisão consciente.*

1️⃣ **Já fiz batismo nas águas (imersão)** e quero me tornar membro  
2️⃣ **Ainda não fiz batismo nas águas (imersão)** *(ou fui batizado quando criança)* e quero me tornar membro  
3️⃣ 🙏 Gostaria de receber orações  
4️⃣ 🕒 Quero saber os horários dos cultos  
5️⃣ 👥 Entrar no grupo do WhatsApp  
6️⃣ ✍️ Outro assunto  

Estou aqui pra caminhar com você! 🙌"""

    adicionar_na_fila(numero, resposta)
    salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)
    atualizar_status(numero, EstadoVisitante.INICIO.value)

    return {
        "resposta": resposta,
        "estado_atual": "SAUDACAO",
        "proximo_estado": EstadoVisitante.INICIO.name
    }


def processar_agradecimento(numero: str, nome_visitante: str, message_sid: str, origem: str = "integra+"):
    """Responde a agradecimentos"""
    resposta = (f"Ficamos felizes em poder ajudar, {nome_visitante}! "
                f"Se precisar de algo mais, estamos à disposição. 🙏")

    adicionar_na_fila(numero, resposta)
    salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)
    atualizar_status(numero, EstadoVisitante.INICIO.value)

    return {
        "resposta": resposta,
        "estado_atual": "AGRADECIMENTO",
        "proximo_estado": EstadoVisitante.INICIO.name
    }
