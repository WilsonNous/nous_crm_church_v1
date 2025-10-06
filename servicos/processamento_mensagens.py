import logging
import re
from database import salvar_conversa, atualizar_status, obter_estado_atual_do_banco, obter_nome_do_visitante, salvar_novo_visitante
from constantes import EstadoVisitante
from utilitarios.texto import normalizar_texto
from utilitarios.identificacao import obter_primeiro_nome
from servicos.fila_mensagens import enviar_mensagem_para_fila
from servicos.saudacoes import detectar_saudacao, processar_saudacao
from servicos.agradecimentos import detectar_agradecimento, processar_agradecimento
from servicos.atendimento_oracao import processar_pedido_oracao
from servicos.atendimento_outros import processar_outro
from servicos.atendimento_eventos import processar_evento_enviado
from servicos.fluxo_transicoes import obter_proximo_estado, obter_mensagem_estado
from servicos.detector_ministerio import detectar_palavra_chave_ministerio
from ia_integracao import IAIntegracao

# IA de apoio
ia_integracao = IAIntegracao()

def processar_mensagem(numero: str, texto_recebido: str, message_sid: str, acao_manual=False, origem="integra+") -> dict:
    """
    Orquestra o fluxo de atendimento do visitante conforme o estado atual e a mensagem recebida.
    """
    logging.info(f"📥 Processando mensagem | Origem={origem} | Numero={numero}, SID={message_sid}, Mensagem={texto_recebido}")

    # Normalização
    numero_normalizado = numero.lstrip("55")  # 🔧 Corrige: banco só guarda número nacional
    texto_normalizado = normalizar_texto(texto_recebido)

    # Salva mensagem recebida
    salvar_conversa(numero_normalizado, texto_recebido, tipo="recebida", sid=message_sid, origem=origem)

    # Estado atual do visitante
    estado_str = obter_estado_atual_do_banco(numero_normalizado)
    estado_atual = EstadoVisitante[estado_str] if estado_str in EstadoVisitante.__members__ else EstadoVisitante.INICIO

    logging.debug(f"📊 Estado atual no banco: {estado_str} → {estado_atual.name}")

    # ========== Palavra-chave de ministério ==========
    resposta_ministerio = detectar_palavra_chave_ministerio(texto_normalizado)
    if resposta_ministerio:
        enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio)
        salvar_conversa(numero_normalizado, resposta_ministerio, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta_ministerio,
            "estado_atual": "MINISTERIO",
            "proximo_estado": "INICIO"
        }

    # ========== Agradecimento ==========
    if detectar_agradecimento(texto_normalizado):
        return processar_agradecimento(numero_normalizado, message_sid, origem)

    # ========== Visitante novo ==========
    if not estado_str:
        resposta = ("Olá! Parece que você ainda não está cadastrado no nosso sistema. "
                    "Para começar, por favor, me diga o seu nome completo.")
        atualizar_status(numero_normalizado, "PEDIR_NOME", origem=origem)
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": "NOVO", "proximo_estado": "PEDIR_NOME"}

    # ========== Saudação ==========
    if detectar_saudacao(texto_normalizado):
        return processar_saudacao(numero_normalizado, message_sid, origem)

    # ========== Evento enviado ==========
    if estado_atual.name == "EVENTO_ENVIADO":
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_evento_enviado(numero_normalizado, visitor_name, message_sid, origem)

    # ========== Pedido de oração ==========
    if estado_atual == EstadoVisitante.PEDIDO_ORACAO:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_pedido_oracao(numero_normalizado, visitor_name, texto_recebido, message_sid, origem)

    # ========== Outro assunto ==========
    if estado_atual == EstadoVisitante.OUTRO:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_outro(numero_normalizado, visitor_name, texto_recebido, message_sid, origem)

    # ========== Fluxo normal de transições ==========
    proximo_estado = obter_proximo_estado(estado_atual, texto_normalizado)

    def detectar_intencao_pastores(texto: str) -> bool:
        """
        Detecta se o visitante está perguntando ou pedindo informação sobre os pastores.
        Ignora contextos neutros ou de teste.
        """
        texto = texto.lower().strip()
    
        # Padrões que indicam pergunta real
        padroes_validos = [
            r"quem (é|são) (os|o|as)? ?pastores?",
            r"quem (são|é) (o|os)? ?pastor(es)?",
            r"qual (é|são) (o|os)? ?pastor(es)?",
            r"quem é o pastor",
            r"quem são os líderes",
            r"pastores? da igreja",
            r"nome dos pastores",
            r"falar com o pastor",
        ]
    
        # Padrões que devem ser ignorados
        padroes_ignorados = [
            r"pastor [a-z]",  # Ex: "Pastor Alisson", "Pastor Fábio"
            r"pastora [a-z]",
            r"teste",
            r"não precisa responder",
            r"mensagem de teste",
        ]
    
        if any(re.search(p, texto) for p in padroes_ignorados):
            return False
    
        return any(re.search(p, texto) for p in padroes_validos)

    # Verifica intenção específica antes do fluxo principal
    if detectar_intencao_pastores(texto_normalizado):
        resposta = (
            "Nossos pastores atuais são:\n"
            "- *Pr. Fábio Ferreira*\n"
            "- *Pra. Cláudia Ferreira*\n\n"
            "Você pode seguir o Pr. Fábio no Instagram: @prfabioferreirasoficial\n"
            "E a Pra. Cláudia em: @claudiaferreiras1"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": estado_atual.name}
    
    if proximo_estado:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta = obter_mensagem_estado(proximo_estado, visitor_name)
        atualizar_status(numero_normalizado, proximo_estado.value, origem=origem)
        enviar_mensagem_para_fila(numero_normalizado, resposta)
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": proximo_estado.name}

    # ========== Fallback para IA ==========
    try:
        resposta_ia, confianca = ia_integracao.responder_pergunta(pergunta_usuario=texto_recebido)
        if resposta_ia and confianca > 0.2:
            enviar_mensagem_para_fila(numero_normalizado, resposta_ia)
            salvar_conversa(numero_normalizado, resposta_ia, tipo="enviada", sid=message_sid, origem=origem)
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value, origem=origem)
            return {"resposta": resposta_ia, "estado_atual": estado_atual.name, "proximo_estado": EstadoVisitante.INICIO.name}
    except Exception as e:
        logging.error(f"❌ Erro IA: {e}")

    # ========== Se nada funcionou ==========
    visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
    resposta = f"Desculpe, {visitor_name}, não entendi sua resposta. Por favor, escolha uma das opções do menu."
    enviar_mensagem_para_fila(numero_normalizado, resposta)
    salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)

    return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": estado_atual.name}
