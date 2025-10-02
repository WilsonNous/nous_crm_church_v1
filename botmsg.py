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

# 🔄 Configurações Z-API
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

# Inicializa a IA (isso pode levar alguns segundos na primeira execução)
ia_integracao = IAIntegracao()

# Lista de números que receberão os pedidos de oração
numero_pedidos_oracao = ['48984949649', '48999449961']
# Número da secretaria que receberá os pedidos de "outros"
numero_outros_secretaria = '48991553619'


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
    """Processa a fila e envia mensagens sequenciais via Z-API"""
    while fila_mensagens:
        numero, mensagem = fila_mensagens.popleft()
        try:
            enviar_mensagem(numero, mensagem)
            time.sleep(2)  # espaçamento entre envios
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem para {numero}: {e}")

# Função para adicionar mensagens à fila
def adicionar_na_fila(numero, mensagem):
    fila_mensagens.append((numero, mensagem))
    if len(fila_mensagens) == 1:
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
    """Envia pedido de oração formatado para os intercessores via Z-API"""
    mensagem = (
        f"📖 Pedido de Oração\n\n"
        f"🙏 Nome: {visitor_name}\n"
        f"📱 Número: {numero_visitante}\n"
        f"📝 Pedido: {texto_recebido}\n"
        f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    for numero in lista_intercessores:
        try:
            numero_normalizado_oracao = normalizar_para_envio(numero)
            enviar_mensagem(numero_normalizado_oracao, mensagem)
        except Exception as e:
            logging.error(f"Erro ao enviar pedido de oração para {numero}: {e}")

# Substitua a chamada direta para `enviar_mensagem` pelo uso da fila
def enviar_mensagem_para_fila(numero_destino, corpo_mensagem):
    adicionar_na_fila(numero_destino, corpo_mensagem)

# Função para verificar se a mensagem contém uma expressão de agradecimento
def detectar_agradecimento(texto):
    palavras_agradecimento = ["obrigado", "obrigada", "grato", "grata",
                              "agradecido", "agradecida", "muito obrigado",
                              "muito obrigada", "amem", "amém", "aleluia",
                              "gloria a deus"]
    texto_normalizado = normalizar_texto(texto)
    return any(palavra in texto_normalizado for palavra in palavras_agradecimento)

def processar_mensagem(numero: str, texto_recebido: str, message_sid: str, acao_manual=False) -> dict:
    logging.info(f"Processando mensagem: {numero}, SID: {message_sid}, Mensagem: {texto_recebido}")
    numero_normalizado = normalizar_para_recebimento(numero)
    texto_recebido_normalizado = normalizar_texto(texto_recebido)

    # Buscar estado atual do visitante no banco de dados
    estado_str = obter_estado_atual_do_banco(numero_normalizado)
    logging.debug(f"Estado atual do visitante no Banco: {estado_str}, Mensagem: {texto_recebido}")

    # Estado atual é validado e fluxo normal continua
    estado_atual = EstadoVisitante[estado_str] if estado_str in EstadoVisitante.__members__ \
        else EstadoVisitante.INICIO
    logging.debug(f"Estado atual: {estado_atual.name}, Texto recebido: {texto_recebido_normalizado}")

    # Se o estado for NULL, ou seja, o visitante não está registrado no sistema
    if not estado_str:
        # Verificar se o estado atual é "PEDIR_NOME" (já foi pedido o nome)
        if estado_str == 'PEDIR_NOME':
            # Salvar o nome e registrar o visitante
            salvar_novo_visitante(numero_normalizado, texto_recebido_normalizado)
            resposta = f"Obrigado, {texto_recebido_normalizado}! Agora podemos continuar com o atendimento."
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)
            proximo_estado = EstadoVisitante.INICIO
        else:
            # Pedir o nome do visitante
            resposta = ("Olá! Parece que você ainda não está cadastrado no nosso sistema. "
                        "Para começar, por favor, me diga o seu nome completo.")
            atualizar_status(numero_normalizado, 'PEDIR_NOME')
            proximo_estado = 'PEDIR_NOME'

        # Enviar a mensagem e salvar a conversa
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada', sid=message_sid)
        return {
            "resposta": resposta,
            "estado_atual": estado_str or "PEDIR_NOME",
            "proximo_estado": proximo_estado
        }

    # Verifica se o texto contém uma palavra-chave de ministério
    resposta_ministerio = detectar_palavra_chave_ministerio(texto_recebido_normalizado)
    if resposta_ministerio:
        enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio)
        salvar_conversa(numero_normalizado, resposta_ministerio, tipo='enviada', sid=message_sid)
        return {
            "resposta": resposta_ministerio,
            "estado_atual": "MINISTERIO",
            "proximo_estado": "INICIO"
        }

    # Verificar se a mensagem é um agradecimento
    if detectar_agradecimento(texto_recebido_normalizado):
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta_agradecimento = (f"Ficamos felizes em poder ajudar, {visitor_name}! "
                                  f"Se precisar de algo mais, estamos à disposição.")
        enviar_mensagem_para_fila(numero_normalizado, resposta_agradecimento)
        salvar_conversa(numero_normalizado, resposta_agradecimento, tipo='enviada', sid=message_sid)
        return {
            "resposta": resposta_agradecimento,
            "estado_atual": "AGRADACIMENTO",
            "proximo_estado": "INICIO"
        }

    # Verificar se a mensagem é uma saudação
    if detectar_saudacao(texto_recebido_normalizado):
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta_saudacao = f"""Olá, {visitor_name}! 😊
    Sou o **Integra+**, seu assistente do Ministério de Integração da Mais de Cristo Canasvieiras.

    Como posso te ajudar hoje?

    1️⃣ Sou batizado e quero me tornar membro
    2️⃣ Não sou batizado e quero me tornar membro
    3️⃣ Gostaria de receber orações
    4️⃣ Quero saber os horários dos cultos
    5️⃣ Entrar no grupo do WhatsApp
    6️⃣ Outro assunto

    Estou aqui pra você! 🙌"""
        enviar_mensagem_para_fila(numero_normalizado, resposta_saudacao)
        salvar_conversa(numero_normalizado, resposta_saudacao, tipo='enviada', sid=message_sid)
        return {
            "resposta": resposta_saudacao,
            "estado_atual": "SAUDACAO",
            "proximo_estado": estado_str or "INICIO"
        }

    if estado_atual == EstadoVisitante.FIM:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta = f"""Que bom ter você de volta, {visitor_name}! 😃 Estamos felizes por poder te ajudar novamente.

Aqui estão algumas opções que você pode escolher:

1⃣ Sou batizado em águas, e quero me tornar membro.
2⃣ Não sou batizado, e quero me tornar membro.
3⃣ Gostaria de receber orações.
4⃣ Queria saber mais sobre os horários dos cultos.
5⃣ Quero entrar no grupo do WhatsApp da igreja.
6⃣ Outro assunto."""
        # Atualiza o status para INICIO e envia a mensagem
        proximo_estado = EstadoVisitante.INICIO
        atualizar_status(numero_normalizado, proximo_estado.value)
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": proximo_estado.name
        }

    # Se o estado for NULL e a ação for manual, enviar a mensagem inicial
    if not estado_str and acao_manual:
        visitor_name = obter_primeiro_nome(obter_nome_do_visitante(numero_normalizado)) or "Visitante"
        resposta_inicial = f"""👋 A Paz de Cristo, {visitor_name}! Tudo bem com você?
    
    Sou o *Integra+*, assistente do Ministério de Integração da MAIS DE CRISTO Canasvieiras.  
    Escolha uma das opções abaixo, respondendo com o número correspondente:
    
    1⃣ Sou batizado em águas e quero me tornar membro.  
    2⃣ Não sou batizado e quero me tornar membro.  
    3⃣ Gostaria de receber orações.  
    4⃣ Quero saber os horários dos cultos.  
    5⃣ Quero entrar no grupo do WhatsApp.  
    6⃣ Outro assunto.  
    
    🙏 Me diga sua escolha para podermos continuar!
    """
        atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)
        enviar_mensagem_para_fila(numero_normalizado, resposta_inicial)
        salvar_conversa(numero_normalizado, resposta_inicial, tipo='enviada', sid=message_sid)
        return {
            "resposta": resposta_inicial,
            "estado_atual": EstadoVisitante.INICIO.name,
            "proximo_estado": EstadoVisitante.INICIO.name
        }


    # Verifica se a mensagem recebida foi a mensagem inicial e não a processa
    if texto_recebido_normalizado.startswith("a paz de cristo") and not acao_manual:
        logging.info(f"Mensagem inicial detectada. Ignorando processamento de resposta "
                     f"para o número {numero_normalizado}")
        return {
            "resposta": None,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    salvar_conversa(numero_normalizado, texto_recebido, tipo='recebida', sid=message_sid)

    # Procurar o próximo estado baseado na resposta numérica ou palavra-chave
    proximo_estado = transicoes.get(estado_atual, {}).get(texto_recebido_normalizado)

    if estado_atual == EstadoVisitante.PEDIDO_ORACAO:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        # Salvando o pedido de oração no banco
        salvar_conversa(numero_normalizado, f"Pedido de oração: {texto_recebido}", tipo='recebida', sid=message_sid)
        # Enviar o pedido de oração para a lista de intercessores usando o template
        enviar_pedido_oracao(
            numero_pedidos_oracao,
            visitor_name,
            numero_normalizado,
            texto_recebido
        )
        # Responder ao visitante que o pedido foi recebido e estamos orando por ele
        resposta = (
            f"Seu pedido de oração foi recebido, {visitor_name}. "
            f"Nossa equipe de intercessão já está orando por você, "
            f"confiamos que Deus está ouvindo. "
            f"Se precisar de mais orações ou apoio, estamos aqui para você. 🙏"
        )
        proximo_estado = EstadoVisitante.FIM
        atualizar_status(numero_normalizado, EstadoVisitante.FIM.value)
        # --- ADICIONE ESTA LINHA ---
        atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)  # Força reset após atendimento
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": EstadoVisitante.FIM.name
        }

    if estado_atual == EstadoVisitante.OUTRO:
        resposta_ministerio = detectar_palavra_chave_ministerio(texto_recebido_normalizado)
        if resposta_ministerio:
            enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio)
            salvar_conversa(numero_normalizado, resposta_ministerio, tipo='enviada', sid=message_sid)
            return {
                "resposta": resposta_ministerio,
                "estado_atual": "MINISTERIO",
                "proximo_estado": "INICIO"
            }
        # Verificar se a mensagem é um agradecimento
        if detectar_agradecimento(texto_recebido_normalizado):
            resposta_agradecimento = ("Ficamos felizes em poder ajudar! "
                                      "Se precisar de algo mais, estamos à disposição.")
            enviar_mensagem_para_fila(numero_normalizado, resposta_agradecimento)
            salvar_conversa(numero_normalizado, resposta_agradecimento, tipo='enviada', sid=message_sid)
            return {
                "resposta": resposta_agradecimento,
                "estado_atual": "AGRADACIMENTO",
                "proximo_estado": "INICIO"
            }
        logging.warning(
            f"Nenhuma transição encontrada para o estado {estado_atual.name} "
            f"com a mensagem '{texto_recebido_normalizado}'.")
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        # Salvando a mensagem de "outro" no banco de dados
        salvar_conversa(numero_normalizado, f"Outro: {texto_recebido}", tipo='recebida', sid=message_sid)
        # Enviar a mensagem para o número da secretaria
        mensagem_outro = (
            f"Solicitação de Atendimento (Outro):\n"
            f"Visitante: {visitor_name}\n"
            f"Número: {numero_normalizado}\n"
            f"Mensagem: {texto_recebido}\n"
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        try:
            numero_normalizado_secretaria = normalizar_para_envio(numero_outros_secretaria)
            adicionar_na_fila(numero_normalizado_secretaria, mensagem_outro)
        except Exception as e:
            logging.error(f"Erro ao enviar a mensagem 'Outro' para o número da secretaria: {e}")
        # Responder ao visitante
        resposta = (f"Entendido, {visitor_name}. Sua solicitação foi encaminhada para a nossa secretaria, "
                    f"e em breve entraremos em contato com você. 🙂")
        proximo_estado = EstadoVisitante.FIM
        atualizar_status(numero_normalizado, EstadoVisitante.FIM.value)
        # --- ADICIONE ESTA LINHA ---
        atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)  # Força reset após atendimento
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": EstadoVisitante.FIM.name
        }

    logging.info(f"O Próximo estado é: {proximo_estado}.")

  # ======================
  # Contexto de Evento Enviado
  # ======================
  if estado_atual.name == "EVENTO_ENVIADO":
      visitor_name = obter_primeiro_nome(obter_nome_do_visitante(numero_normalizado)) or "Visitante"
      resposta = (f"👋 Oi {visitor_name}, vi que você recebeu nosso convite para o evento! 🎉\n"
                  "Gostaria de confirmar sua presença ou saber mais detalhes?\n\n"
                  "Responda com:\n"
                  "1️⃣ Sim, quero participar!\n"
                  "2️⃣ Quero saber mais informações.\n"
                  "3️⃣ Não posso participar desta vez.")
  
      # Resetamos para INICIO para seguir o fluxo normal depois
      atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)
      enviar_mensagem_para_fila(numero_normalizado, resposta)
      salvar_conversa(numero_normalizado, resposta, tipo='enviada', sid=message_sid)
  
      return {
          "resposta": resposta,
          "estado_atual": "EVENTO_ENVIADO",
          "proximo_estado": EstadoVisitante.INICIO.name
      }

  
    # Tratamento para quando nenhuma transição é encontrada
    if proximo_estado is None:
        # --- NOVO: Busca a última pergunta do usuário para contexto ---
                # --- NOVO: Busca a última pergunta do usuário para contexto ---
        ultima_pergunta = None
        try:
            conn = get_db_connection()
            # CORRIGIDO: uso do DictCursor no PyMySQL
            import pymysql
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT mensagem FROM conversas 
                WHERE visitante_id = (SELECT id FROM visitantes WHERE telefone = %s) 
                AND tipo = 'recebida' 
                AND message_sid != %s
                ORDER BY data_hora DESC LIMIT 1
            """, (numero_normalizado, message_sid))
            result = cursor.fetchone()
            if result:
                ultima_pergunta = result['mensagem']
            cursor.close()
            conn.close()
        except Exception as e:
            logging.error(f"Erro ao buscar última pergunta: {e}")


        # --- CORRIGIDO: Chamada correta da IA ---
        resultado_ia = ia_integracao.responder_pergunta(
            pergunta_usuario=texto_recebido
        )

        if resultado_ia[0] and resultado_ia[1] > 0.2:  # resultado_ia[0] = resposta, resultado_ia[1] = confiança
            logging.info(f"IA respondeu com confiança {resultado_ia[1]:.2f}: {resultado_ia[0]}")
            enviar_mensagem_para_fila(numero_normalizado, resultado_ia[0])
            salvar_conversa(numero_normalizado, resultado_ia[0], tipo='enviada', sid=message_sid)
            # Atualiza o estado para INICIO para manter o fluxo
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)
            return {
                "resposta": resultado_ia[0],
                "estado_atual": estado_atual.name,
                "proximo_estado": EstadoVisitante.INICIO.name
            }

        # Se a IA não respondeu, continua com a lógica existente
        # Verifica se a mensagem contém uma palavra-chave de ministério
        resposta_ministerio = detectar_palavra_chave_ministerio(texto_recebido_normalizado)
        if resposta_ministerio:
            enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio)
            salvar_conversa(numero_normalizado, resposta_ministerio, tipo='enviada', sid=message_sid)
            return {
                "resposta": resposta_ministerio,
                "estado_atual": "MINISTERIO",
                "proximo_estado": "INICIO"
            }

        # Verificar se a mensagem é uma saudação
        if detectar_saudacao(texto_recebido_normalizado):
            resposta_saudacao = "Oi! Que bom te ver por aqui 😊. Como posso ajudar você hoje?"
            enviar_mensagem_para_fila(numero_normalizado, resposta_saudacao)
            salvar_conversa(numero_normalizado, resposta_saudacao, tipo='enviada', sid=message_sid)
            return {
                "resposta": resposta_saudacao,
                "estado_atual": "SAUDACAO",
                "proximo_estado": estado_str or "INICIO"
            }

        # Verificar se a mensagem é um agradecimento
        if detectar_agradecimento(texto_recebido_normalizado):
            resposta_agradecimento = ("Ficamos felizes em poder ajudar! "
                                      "Se precisar de algo mais, estamos à disposição.")
            enviar_mensagem_para_fila(numero_normalizado, resposta_agradecimento)
            salvar_conversa(numero_normalizado, resposta_agradecimento, tipo='enviada', sid=message_sid)
            return {
                "resposta": resposta_agradecimento,
                "estado_atual": "AGRADACIMENTO",
                "proximo_estado": "INICIO"
            }

        logging.warning(
            f"Nenhuma transição encontrada para o estado {estado_atual.name} "
            f"com a mensagem '{texto_recebido_normalizado}'.")
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        # Mensagem de erro cordial com o menu inicial
        resposta = f"""Desculpe, {visitor_name}, não entendi sua resposta. Por favor, tente novamente.

Aqui estão algumas opções que você pode escolher:

1⃣ Sou batizado em águas, e quero me tornar membro.
2⃣ Não sou batizado, e quero me tornar membro.
3⃣ Gostaria de receber orações.
4⃣ Queria saber mais sobre os horários dos cultos.
5⃣ Quero entrar no grupo do WhatsApp da igreja.
6⃣ Outro assunto."""
        proximo_estado = estado_atual
    else:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta = mensagens.get(proximo_estado, f"Desculpe, {visitor_name}, não entendi sua resposta.")

    # Atualizar o status se houver mudança de estado
    if proximo_estado != estado_atual:
        atualizar_status(numero_normalizado, proximo_estado.value)
        logging.info(f"Estado atualizado para {proximo_estado.name} no banco de dados para o "
                     f"número {numero_normalizado}")
    else:
        logging.info(f"Estado mantido como {estado_atual.name} para o número {numero_normalizado}")

    # Enviar mensagem de resposta e registrar estatísticas
    try:
        enviar_mensagem_para_fila(numero, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)
    except Exception as e:
        logging.error(f"Erro ao enviar ou salvar mensagem para {numero_normalizado}: {e}")

    return {
        "resposta": resposta,
        "estado_atual": estado_atual.name,
        "proximo_estado": proximo_estado.name
    }

def normalizar_texto(texto):
    texto = texto.strip().lower()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

def validar_data_nascimento(data: str) -> bool:
    """
    Valida se a data de nascimento está no formato DD/MM/AAAA.
    """
    padrao = r"^\d{2}/\d{2}/\d{4}$"
    return re.match(padrao, data) is not None

# =======================
# Função central de envio (Z-API)
# =======================
def enviar_mensagem(numero_destino, corpo_mensagem, imagem_url=None):
    """Envia mensagem de texto ou imagem via Z-API"""
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
        headers = {
            "Client-Token": ZAPI_CLIENT_TOKEN,
            "Content-Type": "application/json"
        }
        if imagem_url:
            payload = {"phone": numero_normalizado, "caption": corpo_mensagem, "image": imagem_url}
            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
        else:
            payload = {"phone": numero_normalizado, "message": corpo_mensagem}
            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

        logging.info(f"➡️ Enviando via Z-API | {numero_normalizado} | {corpo_mensagem[:50]}...")
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if not response.ok:
            logging.error(f"❌ Falha no envio para {numero_normalizado}: {response.status_code} {response.text}")
        else:
            logging.info(f"✅ Mensagem enviada para {numero_normalizado}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem via Z-API: {e}")

# =======================
# Envio manual (mensagens parametrizadas)
# =======================
def enviar_mensagem_manual(numero_destino, titulo, params):
    """
    Envia mensagem "manual" (antes usada com template no Twilio) via Z-API.
    Agora monta um texto formatado com os parâmetros recebidos.
    """
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)

        # Monta a mensagem com título + parâmetros em formato legível
        msg = f"📌 {titulo}\n\n"
        for k, v in params.items():
            msg += f"- {k.capitalize()}: {v}\n"

        enviar_mensagem(numero_normalizado, msg)
        logging.info(f"✅ Mensagem manual enviada para {numero_normalizado}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem manual via Z-API: {e}")

