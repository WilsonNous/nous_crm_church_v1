import unicodedata
import os
import logging
from twilio.rest import Client
from database import (atualizar_status, salvar_conversa, normalizar_para_recebimento,
                      normalizar_para_envio, registrar_estatistica, salvar_novo_visitante,
                      obter_estado_atual_do_banco, obter_nome_do_visitante,
                      get_db_connection)
from datetime import datetime
import time
import threading
from collections import deque
import json
import requests
import re
from ia_integracao import IAIntegracao
from constantes import (EstadoVisitante, mensagens, palavras_chave_ministerios)

# Configurações Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

# Inicializa a IA (isso pode levar alguns segundos na primeira execução)
ia_integracao = IAIntegracao()

# Lista de números que receberão os pedidos de oração
numero_pedidos_oracao = ['48984949649', '48999449961']
# Número da secretaria que receberá os pedidos de "outros"
numero_outros_secretaria = '48991553619'

if not account_sid or not auth_token:
    raise EnvironmentError("Twilio SID e/ou Auth Token não definidos nas variáveis de ambiente.")

client = Client(account_sid, auth_token)

# Transições
transicoes = {
    EstadoVisitante.INICIO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "batizado": EstadoVisitante.INTERESSE_DISCIPULADO,
        "novo começo": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "oração": EstadoVisitante.PEDIDO_ORACAO,
        "horários": EstadoVisitante.HORARIOS,
        "grupo": EstadoVisitante.LINK_WHATSAPP,
        "outro": EstadoVisitante.OUTRO
    },
    EstadoVisitante.INTERESSE_DISCIPULADO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.INTERESSE_NOVO_COMEC: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.PEDIDO_ORACAO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.HORARIOS: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.OUTRO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.LINK_WHATSAPP: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "default": EstadoVisitante.INICIO
    },
    EstadoVisitante.FIM: {
        "default": EstadoVisitante.INICIO
    }
}

# Fila de mensagens
fila_mensagens = deque()

# Função para processar a fila de mensagens
def processar_fila_mensagens():
    while fila_mensagens:
        numero, mensagem = fila_mensagens.popleft()
        try:
            enviar_mensagem(numero, mensagem)
            time.sleep(2)  # Aguarda 2 segundos entre o envio de mensagens
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem para {numero}: {e}")

# Função para adicionar mensagens à fila
def adicionar_na_fila(numero, mensagem):
    fila_mensagens.append((numero, mensagem))
    if len(fila_mensagens) == 1:  # Se a fila estava vazia, processa imediatamente
        threading.Thread(target=processar_fila_mensagens).start()

# Função para capturar apenas o primeiro nome do visitante
def obter_primeiro_nome(nome_completo: str) -> str:
    return nome_completo.split()[0]  # Captura o primeiro nome do visitante

def detectar_palavra_chave_ministerio(texto_recebido: str):
    texto_recebido = normalizar_texto(texto_recebido).replace('ç', 'c')
    for palavra, resposta in palavras_chave_ministerios.items():
        if palavra in texto_recebido or palavra.rstrip('s') in texto_recebido:
            return resposta
    return None

def detectar_saudacao(texto: str) -> bool:
    """
    Verifica se o texto contém uma saudação.
    """
    saudacoes = ["ola", "oi", "bom dia", "boa tarde", "boa noite", "eae", "e aí", "saudações",
                 "a paz do senhor", "a paz de cristo", "paz"]
    texto_normalizado = normalizar_texto(texto)
    for saudacao in saudacoes:
        if saudacao in texto_normalizado:
            return True
    return False

# Função para enviar pedidos de oração para todos os números da lista
def enviar_pedido_oracao(lista_intercessores, visitor_name, numero_visitante, texto_recebido):
    template_sid = 'HX86a5053a56e35cf157726b22b9c89be6'
    for numero in lista_intercessores:
        try:
            numero_normalizado_oracao = normalizar_para_envio(numero)
            params = {
                "visitor_name": visitor_name,
                "numero_normalizado": numero_visitante,
                "texto_recebido": texto_recebido,
                "date": datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            enviar_mensagem_manual(numero_normalizado_oracao, template_sid, params)
        except Exception as e:
            logging.error(f"Erro ao enviar o pedido de oração para o número {numero}: {e}")

# Substitua a chamada direta para `enviar_mensagem` pelo uso da fila
def enviar_mensagem_para_fila(numero_destino, corpo_mensagem):
    adicionar_na_fila(numero_destino, corpo_mensagem)

# Função para verificar se a mensagem contém uma expressão de agradecimento
def detectar_agradecimento(texto):
    palavras_agradecimento = ["obrigado", "obrigada", "grato", "grata",
                              "agradecido", "agradecida", "muito obrigado",
                              "muito obrigada", "amem", "amém", "aleluia",
                              "gloria
