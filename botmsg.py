import unicodedata
import os
import logging
from twilio.rest import Client
from database import (atualizar_status, salvar_conversa, normalizar_para_recebimento,
                      normalizar_para_envio, registrar_estatistica, salvar_novo_visitante,
                      obter_estado_atual_do_banco, obter_nome_do_visitante, obter_dados_visitante,
                      atualizar_dado_visitante)
from enum import Enum
from datetime import datetime
import time
import threading
from collections import deque
import json
import requests
import re
from ia_integracao import IAIntegracao

# Configurações Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')

# Configuração do banco de dados para a IA
db_config_ia = {
    'host': 'localhost',  # Altere para o seu host
    'user': 'seu_usuario',  # Altere para seu usuário
    'password': 'sua_senha',  # Altere para sua senha
    'database': 'seu_banco'   # Altere para seu banco
}

# Inicializa a IA (isso pode levar alguns segundos na primeira execução)
ia_integracao = IAIntegracao(db_config_ia)

# Lista de números que receberão os pedidos de oração
numero_pedidos_oracao = ['48984949649', '48999449961']

# Número da secretaria que receberá os pedidos de "outros"
numero_outros_secretaria = '48991553619'

if not account_sid or not auth_token:
    raise EnvironmentError("Twilio SID e/ou Auth Token não definidos nas variáveis de ambiente.")

client = Client(account_sid, auth_token)

# Definição dos links (fora da classe EstadoVisitante)
link_grupo = \
    "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK"
link_discipulado = \
    "https://forms.gle/qdxNnPyCfKoJeseU8"
link_discipulado_novosComec = \
    "https://forms.gle/Cm7d5F9Zv77fgJKDA"
link_grupo_homens_corajosos = "https://chat.whatsapp.com/H4pFqtsruDr0QJ1NvCMjda"
link_grupo_transformadas = "https://chat.whatsapp.com/LT0pN2SPTqf66yt3AWKIAe"


# Enum para os diferentes estados do visitante
class EstadoVisitante(Enum):
    ATUALIZANDO = "ATUALIZANDO"
    INICIO = "INICIO"
    INTERESSE_DISCIPULADO = "INTERESSE_DISCIPULADO"
    INTERESSE_NOVO_COMEC = "INTERESSE_NOVO_COMEC"
    PEDIDO_ORACAO = "PEDIDO_ORACAO"
    HORARIOS = "HORARIOS"
    LINK_WHATSAPP = "LINK_WHATSAPP"
    OUTRO = "OUTRO"
    ATUALIZAR_CADASTRO = "ATUALIZAR_CADASTRO"
    ATUALIZAR_NOME = "ATUALIZAR_NOME"
    ATUALIZAR_EMAIL = "ATUALIZAR_EMAIL"
    ATUALIZAR_DATA_NASCIMENTO = "ATUALIZAR_DATA_NASCIMENTO"
    ATUALIZAR_CIDADE = "ATUALIZAR_CIDADE"
    ATUALIZAR_GENERO = "ATUALIZAR_GENERO"
    ATUALIZAR_ESTADO_CIVIL = "ATUALIZAR_ESTADO_CIVIL"
    ATUALIZAR_OUTRO = "ATUALIZAR_OUTRO"  # Novo estado para outros campos
    FINALIZAR_ATUALIZACAO = "FINALIZAR_ATUALIZACAO"
    AGUARDANDO_ATUALIZACAO = "AGUARDANDO_ATUALIZACAO"
    FIM = "FIM"


transicoes = {
    EstadoVisitante.INICIO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
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
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.INTERESSE_NOVO_COMEC: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.PEDIDO_ORACAO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.HORARIOS: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,  # Permanece no estado atual
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.OUTRO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.LINK_WHATSAPP: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "default": EstadoVisitante.INICIO  # Volta ao menu inicial
    },
    EstadoVisitante.ATUALIZAR_CADASTRO: {
        "1": EstadoVisitante.INTERESSE_DISCIPULADO,
        "2": EstadoVisitante.INTERESSE_NOVO_COMEC,
        "3": EstadoVisitante.PEDIDO_ORACAO,
        "4": EstadoVisitante.HORARIOS,
        "5": EstadoVisitante.LINK_WHATSAPP,
        "6": EstadoVisitante.OUTRO,
        "7": EstadoVisitante.ATUALIZAR_CADASTRO,
        "nome": EstadoVisitante.ATUALIZAR_NOME,
        "email": EstadoVisitante.ATUALIZAR_EMAIL,
        "endereço": EstadoVisitante.ATUALIZAR_CIDADE,
        "gênero": EstadoVisitante.ATUALIZAR_GENERO,
        "estado civil": EstadoVisitante.ATUALIZAR_ESTADO_CIVIL,
    },
    EstadoVisitante.ATUALIZAR_GENERO: {
        "masculino": EstadoVisitante.FINALIZAR_ATUALIZACAO,
        "feminino": EstadoVisitante.FINALIZAR_ATUALIZACAO,
        "outro": EstadoVisitante.FINALIZAR_ATUALIZACAO,
    },
    EstadoVisitante.ATUALIZAR_ESTADO_CIVIL: {
        "casado": EstadoVisitante.FINALIZAR_ATUALIZACAO,
        "solteiro": EstadoVisitante.FINALIZAR_ATUALIZACAO,
        "divorciado": EstadoVisitante.FINALIZAR_ATUALIZACAO,
        "viúvo": EstadoVisitante.FINALIZAR_ATUALIZACAO,
    },
    EstadoVisitante.FIM: {
        "default": EstadoVisitante.INICIO  # Qualquer mensagem após FIM leva ao INICIO com saudação de retorno
    }
}


# Mensagens associadas aos estados
mensagens = {
    EstadoVisitante.INICIO: "Escolha uma das opções:\n"
                            "1⃣ Sou batizado em águas, e quero me tornar membro.\n"
                            "2⃣ Não sou batizado, e quero me tornar membro.\n"
                            "3⃣ Gostaria de receber orações.\n"
                            "4⃣ Queria saber mais sobre os horários dos cultos.\n"
                            "5⃣ Quero entrar no grupo do WhatsApp da igreja.\n"
                            "6⃣ Outro assunto.\n"
                            "7⃣ Atualizar meu cadastro.",
    EstadoVisitante.INTERESSE_DISCIPULADO: f"Que ótimo! Como você já foi batizado, você pode participar do nosso "
                                           f"Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                                           f"{link_discipulado}. Estamos muito felizes com seu interesse em se tornar "
                                           f"parte da nossa família espiritual!",

    EstadoVisitante.INTERESSE_NOVO_COMEC: f"Ficamos felizes com o seu interesse! Como você ainda não foi batizado,"
                                          f" recomendamos que participe do nosso Discipulado Novo Começo, "
                                          f"onde você aprenderá mais sobre a fé e os próximos passos. "
                                          f"Aqui está o link para se inscrever: {link_discipulado_novosComec}. "
                                          f"Estamos à disposição para te ajudar nesse caminho!",

    # Modificar a mensagem de pedido de oração para ser mais humanizada
    EstadoVisitante.PEDIDO_ORACAO: "Ficamos honrados em receber o seu pedido de oração. "
                                   "Sinta-se à vontade para compartilhar o que está em seu coração. "
                                   "Estamos aqui para orar junto com você e apoiar no que for preciso. 🙏",

    EstadoVisitante.HORARIOS: (
        "*Seguem nossos horários de cultos:*\n\n"
        "🌿 *Domingo* - Culto da Família - às 19h\n"
        "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção. "
        "\"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*\n\n"

        "🔥 *Quinta Fé* - Culto dos Milagres - às 20h\n"
        "Um encontro de fé para vivermos o sobrenatural de Deus. "
        "\"Tudo é possível ao que crê.\" *(Marcos 9:23)*\n\n"

        "🎉 *Sábado* - Culto Alive - às 20h\n"
        "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
        "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*\n\n"

        "🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
        "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" *(Mateus 18:20)*\n\n"

        "Gostaria de mais informações?"),

    EstadoVisitante.LINK_WHATSAPP: f"Aqui está o link para entrar no nosso grupo do WhatsApp: {link_grupo}\n"
                                   "Agradecemos seu contato e esperamos vê-lo em breve!",

    EstadoVisitante.OUTRO: "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                           "Estamos aqui para ouvir e apoiar você!",

    EstadoVisitante.FIM: "Muito obrigado pelo seu contato, {visitor_name}! 🙏 "
                         "Se precisar de mais alguma coisa, estaremos sempre aqui para você. "
                         "Que Deus te abençoe e até breve! 👋",

    EstadoVisitante.ATUALIZAR_CADASTRO: "Você escolheu atualizar seu cadastro. 😊\n\n"
                                        "Antes de prosseguir, gostaria de ver os dados "
                                        "que temos cadastrados para você?\n\n"
                                        "Digite 1 - para **Sim** para ver seus dados ou "
                                        "2 - para **Não** para voltar ao menu inicial.",
}


palavras_chave_ministerios = {
    "homens": "Paz de Cristo, somos os Homens Corajosos da Mais de Cristo Canasvieiras, "
              "nossa missão é servir a Deus com toda força e coração, nos colocando a frente dos propósitos de Deus, "
              "para sermos, sacerdotes da nossa casa, homens de coragem e temente a Deus.\n"
              "Venha fazer parte deste exército e ficar mais próximo do seu propósito.\n\n"
              "Segue link do grupo de whatsapp: " + link_grupo_homens_corajosos,
    "mulheres": "Paz de Cristo, somos o Ministério Mulheres Transformadas da Mais de Cristo Canasvieiras. "
                "Nosso objetivo é promover o crescimento espiritual das mulheres, fortalecendo nossa fé e "
                "nos unindo em amor e comunhão. Temos encontros mensais cheios de aprendizado e inspiração.\n\n"
                "Venha fazer parte deste grupo e viver os propósitos que Deus tem para sua vida.\n\n"
                "Segue link do grupo de whatsapp: " + link_grupo_transformadas,
    "jovens": "O Ministério Alive é dedicado aos jovens e adolescentes, com cultos vibrantes e cheios de propósito.",
    "criancas": "Venha fazer a diferença na vida das crianças! "
                "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "kids": "Venha fazer a diferença na vida das crianças! "
            "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "infantil": "Venha fazer a diferença na vida das crianças! "
                "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "21 dias": "Olá! Ficamos felizes com seu interesse nos 21 dias de oração. 🙏 "
               "Este evento acontece diariamente, das 23h às 23:30, na igreja, e seguirá até o dia 20 de novembro."
               "Será um tempo especial para buscar paz, inspiração e fortalecer a fé. "
               "Caso precise de mais informações ou queira confirmar presença, estou aqui para ajudar!",
    "pastor": "Nossos pastores atuais são:\n"
              "- *Pr Fábio Ferreira*\n"
              "- *Pra Cláudia Ferreira*\n\n"
              "Você pode seguir o *_Pr Fábio Ferreira_* no Instagram: _@prfabioferreirasoficial_\n"
              "E a *_Pra Cláudia Ferreira_* no Instagram: _@claudiaferreiras1_",
    "mais amor": "O Ministério Mais Amor é focado em ações sociais, ajudando os necessitados da nossa comunidade.",
    "gc":     "*Grupos de Comunhão (GC)* - _Pequenos encontros semanais nos lares para compartilhar histórias,_"
              " _oração e comunhão._ "
              "Participe e viva momentos de fé e crescimento espiritual!\n\n"
              "*Inscreva-se aqui:* "
              "https://docs.google.com/forms/d/e/1FAIpQLSdj0b3PF-3jwt9Fsw8FvOxv6rSheN7POC1e0bDzub6vEWJm2A/viewform"
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
    texto_recebido = normalizar_texto(texto_recebido).replace('ç', 'c')  # Normaliza o texto e substitui 'ç' por 'c'
    for palavra, resposta in palavras_chave_ministerios.items():
        if palavra in texto_recebido or palavra.rstrip('s') in texto_recebido:  # Verifica singular/plural
            return resposta
    return None


def detectar_saudacao(texto: str) -> bool:
    """
    Verifica se o texto contém uma saudação.
    """
    saudacoes = ["ola", "oi", "bom dia", "boa tarde", "boa noite", "eae", "e aí", "saudações",
                 "a paz do senhor", "a paz de cristo", "paz"]
    texto_normalizado = normalizar_texto(texto)

    # Verifica se alguma das saudações está presente no texto
    for saudacao in saudacoes:
        if saudacao in texto_normalizado:
            return True
    return False


# Função para enviar pedidos de oração para todos os números da lista
def enviar_pedido_oracao(lista_intercessores, visitor_name, numero_visitante, texto_recebido):
    template_sid = 'HX86a5053a56e35cf157726b22b9c89be6'  # Template SID do pedido de oração
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
                              "gloria a deus"]
    texto_normalizado = normalizar_texto(texto)  # Usar a função de normalização de texto já existente
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
            resposta = ("Olá! Parece que você ainda não está cadastrado no nosso sistema."
                        " Para começar, por favor, me diga o seu nome completo.")
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
        resposta_saudacao = (f"Oi! Que bom te ver por aqui,  {visitor_name}😊. \n\n Como posso ajudar você hoje?\n\n"
                             "Aqui estão algumas opções que você pode escolher:\n\n"
                             "1⃣ Sou batizado em águas, e quero me tornar membro.\n"
                             "2⃣ Não sou batizado, e quero me tornar membro.\n"
                             "3⃣ Gostaria de receber orações.\n"
                             "4⃣ Queria saber mais sobre os horários dos cultos.\n"
                             "5⃣ Quero entrar no grupo do WhatsApp da igreja.\n"
                             "6⃣ Outro assunto.\n")
        enviar_mensagem_para_fila(numero_normalizado, resposta_saudacao)
        salvar_conversa(numero_normalizado, resposta_saudacao, tipo='enviada', sid=message_sid)
        
        return {
            "resposta": resposta_saudacao,
            "estado_atual": "SAUDACAO",
            "proximo_estado": estado_str or "INICIO"
        }

    if estado_atual == EstadoVisitante.FIM:
        # Responder com uma saudação de retorno ao visitante
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]  # Pegando só o primeiro nome
        resposta = (f"Que bom ter você de volta, {visitor_name}! 😃 Estamos felizes por poder te ajudar novamente.\n\n"
                    "Aqui estão algumas opções que você pode escolher:\n\n"
                    "1⃣ Sou batizado em águas, e quero me tornar membro.\n"
                    "2⃣ Não sou batizado, e quero me tornar membro.\n"
                    "3⃣ Gostaria de receber orações.\n"
                    "4⃣ Queria saber mais sobre os horários dos cultos.\n"
                    "5⃣ Quero entrar no grupo do WhatsApp da igreja.\n"
                    "6⃣ Outro assunto.\n")

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

        resposta_inicial = (f"A Paz de Cristo, {visitor_name}! Tudo bem com você?\n\n"
                            "Aqui é a Equipe de Integração da MAIS DE CRISTO Canasvieiras!\n\n"
                            "Escolha uma das opções abaixo, respondendo com o número correspondente:\n\n"
                            "1⃣ Sou batizado em águas, e quero me tornar membro.\n"
                            "2⃣ Não sou batizado, e quero me tornar membro.\n"
                            "3⃣ Gostaria de receber orações.\n"
                            "4⃣ Queria saber mais sobre os horários dos cultos.\n"
                            "5⃣ Quero entrar no grupo do WhatsApp da igreja.\n"
                            "6⃣ Outro assunto.\n\n"
                            "Nos diga qual sua escolha! 🙏")

        # Atualiza o status diretamente para INICIO, sem o MENU
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
            numero_pedidos_oracao,  # Lista de números dos intercessores
            visitor_name,  # Nome do visitante
            numero_normalizado,  # Número do visitante
            texto_recebido  # Texto do pedido
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
            f"Solicitação de Atendimento (Outro):\nVisitante: {visitor_name}\nNúmero: {numero_normalizado}\n"
            f"Mensagem: {texto_recebido}\nData: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
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
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)

        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": EstadoVisitante.FIM.name
        }

    logging.info(f"O Próximo estado é: {proximo_estado}.")

    if proximo_estado == EstadoVisitante.ATUALIZAR_CADASTRO:
        logging.info(f"Processando estado ATUALIZAR_CADASTRO para o número {numero_normalizado}.")

        # Pergunta se o visitante deseja ver os dados cadastrais
        resposta = (
            "Você escolheu atualizar seu cadastro. 😊\n\n"
            "Antes de prosseguir, gostaria de ver os dados que temos cadastrados para você?\n\n"
            "Digite **Sim** para ver seus dados ou **Não** para voltar ao menu inicial."
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        logging.info(f"Enviando mensagem: {resposta}")
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO.value)
        registrar_estatistica(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO,
                              EstadoVisitante.AGUARDANDO_ATUALIZACAO)
        logging.info(f"Salvando a estatistica Status atual é: {estado_atual} e o Próximo estado é: {proximo_estado}.")

        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": proximo_estado.name
        }

    if estado_atual == EstadoVisitante.ATUALIZAR_CADASTRO:
        logging.info(f"Processando estado AGUARDANDO_CONFIRMACAO para o número {numero_normalizado}.")
        texto_recebido_normalizado = normalizar_texto(texto_recebido)

        if texto_recebido_normalizado in ["sim", "s"]:
            # Busca os dados do visitante
            dados = obter_dados_visitante(numero_normalizado)
            logging.info(f"Dados obtidos para o telefone {numero_normalizado}: {dados}")

            if dados:
                # Obtém o nome do visitante
                nome_visitante = dados.get('nome', 'Visitante').split()[0]  # Pega apenas o primeiro nome

                # Constrói a mensagem personalizada
                resposta = (
                    f"Olá, {nome_visitante}! 😊\n\n"
                    f"Aqui estão os dados que temos cadastrados para você:\n\n"
                    f"👤 **Nome:** {dados['nome']}\n"
                    f"📧 **Email:** {dados['email']}\n"
                    f"🎂 **Data de Nascimento:** {dados['data_nascimento']}\n"
                    f"🏙️ **Cidade:** {dados['cidade']}\n"
                    f"⚧️ **Gênero:** {dados['genero']}\n"
                    f"💍 **Estado Civil:** {dados['estado_civil']}\n\n"
                    "Se algum desses dados estiver incorreto ou desatualizado, "
                    "por favor, me informe qual deles você deseja atualizar.\n\n"
                    "Você pode digitar uma das opções abaixo:\n"
                    "- Nome\n"
                    "- Email\n"
                    "- Data de Nascimento\n"
                    "- Cidade\n"
                    "- Gênero\n"
                    "- Estado Civil\n\n"
                    "Estamos aqui para ajudar! 😉"
                )
                # Atualiza o estado para AGUARDANDO_ATUALIZACAO
                proximo_estado = EstadoVisitante.AGUARDANDO_ATUALIZACAO
                atualizar_status(numero_normalizado, proximo_estado.value)

            else:
                # Caso os dados não sejam encontrados
                resposta = (
                    f"Olá! 😊\n\n"
                    "Parece que não encontramos seus dados no sistema. "
                    "Deseja realizar um novo cadastro? (Sim/Não)"
                )
                # Retorna ao estado INICIO
                proximo_estado = 'PEDIR_NOME'
                atualizar_status(numero_normalizado, proximo_estado)

        elif texto_recebido_normalizado in ["não", "nao", "n"]:
            # Retorna ao menu inicial
            resposta = "Tudo bem! Se precisar de algo mais, estou à disposição. 😊"
            proximo_estado = EstadoVisitante.FIM
            atualizar_status(numero_normalizado, proximo_estado.value)

        else:
            # Resposta inválida
            resposta = ("Desculpe, não entendi sua resposta. Digite **Sim** para ver seus dados "
                        "ou **Não** para voltar ao menu inicial.")
            proximo_estado = EstadoVisitante.ATUALIZAR_CADASTRO  # Mantém o mesmo estado

        # Envia a mensagem e salva a conversa
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        logging.info(f"Enviando mensagem: {resposta}")
        salvar_conversa(numero_normalizado, resposta, tipo='enviada')
        registrar_estatistica(numero_normalizado, estado_atual.value, proximo_estado.value)

        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": proximo_estado.name
        }

    # Tratamento da escolha de atualização
    if estado_atual == EstadoVisitante.AGUARDANDO_ATUALIZACAO:
        campo_atualizar = texto_recebido_normalizado.lower()

        if campo_atualizar == "nome":
            mensagem_resposta = "Por favor, informe seu novo nome."
            proximo_estado = EstadoVisitante.ATUALIZAR_NOME
            atualizar_status(numero_normalizado, proximo_estado.value)
        elif campo_atualizar == "email":
            mensagem_resposta = "Por favor, informe seu novo email."
            proximo_estado = EstadoVisitante.ATUALIZAR_EMAIL
            atualizar_status(numero_normalizado, proximo_estado.value)
        elif campo_atualizar == "data de nascimento":
            mensagem_resposta = "Por favor, informe sua nova data de nascimento (no formato DD/MM/AAAA)."
            proximo_estado = EstadoVisitante.ATUALIZAR_DATA_NASCIMENTO
            atualizar_status(numero_normalizado, proximo_estado.value)
        elif campo_atualizar == "cidade":
            mensagem_resposta = "Por favor, informe sua nova cidade."
            proximo_estado = EstadoVisitante.ATUALIZAR_CIDADE
            atualizar_status(numero_normalizado, proximo_estado.value)
        elif campo_atualizar == "gênero":
            mensagem_resposta = ("Por favor, escolha uma das opções abaixo para atualizar seu gênero:"
                                 "\n1️⃣ Masculino\n2️⃣ Feminino\n3️⃣ Outro")
            proximo_estado = EstadoVisitante.ATUALIZAR_GENERO
            atualizar_status(numero_normalizado, proximo_estado.value)
        elif campo_atualizar == "estado civil":
            mensagem_resposta = ("Por favor, escolha uma das opções abaixo para atualizar seu estado civil:"
                                 "\n1️⃣ Casado\n2️⃣ Solteiro\n3️⃣ Divorciado\n4️⃣ Viúvo")
            proximo_estado = EstadoVisitante.ATUALIZAR_ESTADO_CIVIL
            atualizar_status(numero_normalizado, proximo_estado.value)
        else:
            mensagem_resposta = ("Desculpe, não reconheço essa opção. "
                                 "Você pode atualizar: nome, email, data de nascimento, "
                                 "cidade, gênero ou estado civil.")

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')
    elif estado_atual == EstadoVisitante.ATUALIZAR_NOME:
        if texto_recebido_normalizado:
            atualizar_dado_visitante(numero_normalizado, "nome", texto_recebido_normalizado)
            mensagem_resposta = f"Seu nome foi atualizado para: {texto_recebido_normalizado}."
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = "Nome inválido. Por favor, informe seu novo nome."

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    elif estado_atual == EstadoVisitante.ATUALIZAR_EMAIL:
        if texto_recebido_normalizado:
            atualizar_dado_visitante(numero_normalizado, "email", texto_recebido_normalizado)
            mensagem_resposta = f"Seu email foi atualizado para: {texto_recebido_normalizado}."
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = "Email inválido. Por favor, informe seu novo email."

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    elif estado_atual == EstadoVisitante.ATUALIZAR_DATA_NASCIMENTO:
        if validar_data_nascimento(texto_recebido_normalizado):  # Função para validar a data
            atualizar_dado_visitante(numero_normalizado, "data_nascimento", texto_recebido_normalizado)
            mensagem_resposta = f"Sua data de nascimento foi atualizada para: {texto_recebido_normalizado}."
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = "Data de nascimento inválida. Por favor, informe no formato DD/MM/AAAA."

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    elif estado_atual == EstadoVisitante.ATUALIZAR_CIDADE:
        if texto_recebido_normalizado:
            atualizar_dado_visitante(numero_normalizado, "cidade", texto_recebido_normalizado)
            mensagem_resposta = f"Sua cidade foi atualizada para: {texto_recebido_normalizado}."
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = "Cidade inválida. Por favor, informe sua nova cidade."

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    elif estado_atual == EstadoVisitante.ATUALIZAR_GENERO:
        opcoes_genero = {"1": "Masculino", "2": "Feminino", "3": "Outro"}
        genero_escolhido = opcoes_genero.get(texto_recebido_normalizado)

        if genero_escolhido:
            atualizar_dado_visitante(numero_normalizado, "genero", genero_escolhido)
            mensagem_resposta = (f"Seu gênero foi atualizado para: {genero_escolhido}. "
                                 f"Se precisar alterar mais algo, digite a opção desejada.")
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = "Opção inválida. Escolha uma opção válida: 1️⃣ Masculino, 2️⃣ Feminino, 3️⃣ Outro"

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    elif estado_atual == EstadoVisitante.ATUALIZAR_ESTADO_CIVIL:
        opcoes_estado_civil = {"1": "Casado", "2": "Solteiro", "3": "Divorciado", "4": "Viúvo"}
        estado_civil_escolhido = opcoes_estado_civil.get(texto_recebido_normalizado)

        if estado_civil_escolhido:
            atualizar_dado_visitante(numero_normalizado, "estado_civil", estado_civil_escolhido)
            mensagem_resposta = (f"Seu estado civil foi atualizado para: {estado_civil_escolhido}."
                                 f" Se precisar alterar mais algo, digite a opção desejada.")
            atualizar_status(numero_normalizado, EstadoVisitante.ATUALIZAR_CADASTRO)
        else:
            mensagem_resposta = ("Opção inválida. Escolha uma opção válida: "
                                 "1️⃣ Casado, 2️⃣ Solteiro, 3️⃣ Divorciado, 4️⃣ Viúvo")

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    if estado_atual == EstadoVisitante.FINALIZAR_ATUALIZACAO:
        if texto_recebido_normalizado == "finalizar":
            mensagem_resposta = ("Obrigado por atualizar seus dados! "
                                 "Se precisar de mais alguma coisa, estamos aqui para ajudar. 🙌")
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO)
        else:
            mensagem_resposta = ("Se deseja atualizar mais alguma informação, informe qual. "
                                 "Caso tenha finalizado, digite 'finalizar'.")

        enviar_mensagem_para_fila(numero_normalizado, mensagem_resposta)
        salvar_conversa(numero_normalizado, mensagem_resposta, tipo='enviada')

    # Tratamento para quando nenhuma transição é encontrada
    if proximo_estado is None:
        # --- NOVO: Consulta a IA antes de qualquer outra coisa ---
        resposta_ia, confianca_ia = ia_integracao.responder_pergunta(texto_recebido)
        if resposta_ia and confianca_ia > 0.3:  # Limiar de confiança configurável
            logger.info(f"IA respondeu com confiança {confianca_ia:.2f}")
            enviar_mensagem_para_fila(numero_normalizado, resposta_ia)
            salvar_conversa(numero_normalizado, resposta_ia, tipo='enviada', sid=message_sid)
            # Atualiza o estado para INICIO para manter o fluxo
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value)
            return {
                "resposta": resposta_ia,
                "estado_atual": estado_atual.name,
                "proximo_estado": EstadoVisitante.INICIO.name
            }
        # --- FIM DA NOVA SEÇÃO ---
    
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
        resposta = (f"Desculpe, {visitor_name}, não entendi sua resposta. Por favor, tente novamente.\n\n"
                    "Aqui estão algumas opções que você pode escolher:\n\n"
                    "1⃣ Sou batizado em águas, e quero me tornar membro.\n"
                    "2⃣ Não sou batizado, e quero me tornar membro.\n"
                    "3⃣ Gostaria de receber orações.\n"
                    "4⃣ Queria saber mais sobre os horários dos cultos.\n"
                    "5⃣ Quero entrar no grupo do WhatsApp da igreja.\n"
                    "6⃣ Outro assunto.\n")
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


def enviar_mensagem(numero_destino, corpo_mensagem):
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
        logging.info(f"Enviando mensagem para o número normalizado: whatsapp:+{numero_normalizado}")

        mensagem = client.messages.create(
            body=corpo_mensagem,
            from_=f"whatsapp:{twilio_phone_number}",
            to=f"whatsapp:+{numero_normalizado}"
        )
        logging.info(f"Mensagem enviada: {mensagem.sid}")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem para {numero_destino}: {e}")


def enviar_mensagem_manual(numero_destino, template_sid, params):  # Altere o segundo parâmetro para template_sid
    try:
        numero_normalizado = normalizar_para_envio(numero_destino)
        logging.info(f"Enviando mensagem para o número normalizado: whatsapp:+{numero_normalizado}")

        if 'visitor_name' not in params:
            logging.error("A variável 'visitor_name' não foi encontrada em params.")
            return

        logging.info(f"Conteúdo das variáveis: {params}")

        url = f"https://api.twilio.com/2010-04-01/Accounts/{os.environ['TWILIO_ACCOUNT_SID']}/Messages.json"

        data = {
            "To": f"whatsapp:+{numero_normalizado}",
            "From": f"whatsapp:{twilio_phone_number}",
            "ContentSid": template_sid,  # Mude TemplateSid para ContentSid
            "ContentVariables": json.dumps(params)
        }

        response = requests.post(
            url,
            data=data,
            auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        )

        if response.status_code != 201:
            logging.error(f"Erro no envio: {response.status_code} - {response.text}")

        if response.status_code == 201:
            logging.info("Mensagem enviada com sucesso!")

    except Exception as e:
        logging.error(f"Erro ao enviar mensagem para {numero_destino}: {e}")

