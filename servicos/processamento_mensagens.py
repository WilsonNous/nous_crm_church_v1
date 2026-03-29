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

def processar_mensagem(numero: str, texto_recebido: str, message_sid: str, acao_manual=False, origem="integra+", is_webhook_reply: bool = False) -> dict:
    """
    Orquestra o fluxo de atendimento do visitante conforme o estado atual e a mensagem recebida.
    
    Args:
        is_webhook_reply: Se True, marca respostas do bot como conversacionais (is_reply=True no meta)
                         Padrão: False para compatibilidade com chamadas manuais
    """
    logging.info(f"📥 Processando mensagem | Origem={origem} | Numero={numero}, SID={message_sid}, Mensagem={texto_recebido[:80]}... | is_webhook_reply={is_webhook_reply}")

    # Normalização
    numero_normalizado = numero.lstrip("55")  # 🔧 Corrige: banco só guarda número nacional
    texto_normalizado = normalizar_texto(texto_recebido)

    # Salva mensagem recebida
    salvar_conversa(numero_normalizado, texto_recebido, tipo="recebida", sid=message_sid, origem=origem)

    # Estado atual do visitante
    estado_str = obter_estado_atual_do_banco(numero_normalizado)
    estado_atual = EstadoVisitante[estado_str] if estado_str in EstadoVisitante.__members__ else EstadoVisitante.INICIO

    logging.debug(f"📊 Estado atual no banco: {estado_str} → {estado_atual.name}")

    # Helper para criar meta com is_reply
    def _criar_meta(tipo="bot"):
        return {
            "origem": origem,
            "tipo": tipo,
            "is_reply": is_webhook_reply,  # ← Marca como resposta conversacional se for webhook
            "telefone_raw": numero_normalizado,
            "sid_origem": message_sid,
        }

    # ========== Palavra-chave de ministério ==========
    resposta_ministerio = detectar_palavra_chave_ministerio(texto_normalizado)
    if resposta_ministerio:
        enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio, meta=_criar_meta())
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
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": "NOVO", "proximo_estado": "PEDIR_NOME"}

    # ========== Saudação ==========
    if detectar_saudacao(texto_normalizado):
        return processar_saudacao(numero_normalizado, message_sid, origem)

    # ========== Evento enviado ==========
    if estado_atual.name == "EVENTO_ENVIADO":
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_evento_enviado(numero_normalizado, visitor_name, message_sid, origem)

    # ========== Novo tratamento direto da opção 3 (Pedido de Oração) ==========
    if texto_normalizado in ["3", "3.", "3️⃣", "pedido de oração", "pedido de oracao"]:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        texto_pedido_generico = "Pedido de oração solicitado pelo visitante."
        
        logging.info(f"🙏 Pedido de oração automático iniciado para {visitor_name} ({numero_normalizado})")

        # Processa automaticamente o pedido genérico
        return processar_pedido_oracao(
            numero=numero_normalizado,
            nome_visitante=visitor_name,
            texto_recebido=texto_pedido_generico,
            message_sid=message_sid,
            origem=origem
        )

    # ========== Pedido de oração (mensagem complementar) ==========
    if estado_atual == EstadoVisitante.PEDIDO_ORACAO:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_pedido_oracao(numero_normalizado, visitor_name, texto_recebido, message_sid, origem)

    # ========== Outro assunto ==========
    if estado_atual == EstadoVisitante.OUTRO:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_outro(numero_normalizado, visitor_name, texto_recebido, message_sid, origem)

    # ========== Fluxo normal de transições ==========
    proximo_estado = obter_proximo_estado(estado_atual, texto_normalizado)

    # ==========================================================
    # 🔍 DETECÇÕES ESPECÍFICAS (ORDEM IMPORTANTE!)
    # ==========================================================
    
    # 🎯 PRIORIDADE 1: Falar com pastores / secretaria / agendar visita
    # ✅ Esta detecção deve vir ANTES de detectar_intencao_pastores
    def detectar_intencao_falar_pastores(texto: str) -> bool:
        """
        Detecta se o visitante quer entrar em contato direto com os pastores ou secretaria.
        """
        texto = texto.lower().strip()
        
        padroes = [
            r"falar (com|para) (os )?pastor(es)?",
            r"falar (com|para) (a )?secretaria",
            r"contato (com|dos )?pastor(es)?",
            r"contato (com|da )?secretaria",
            r"ligar (para|pros )?pastor(es)?",
            r"ligar (para|pra )?secretaria",
            r"whatsapp (dos )?pastor(es)?",
            r"whatsapp (da )?secretaria",
            r"agenda (com|dos )?pastor(es)?",
            r"agendar (com|uma visita com )?pastor",
            r"marcar (com|uma visita com )?pastor",
            r"visita pastoral",
            r"visita dos pastores",
            r"como falo com os pastores",
            r"como entro em contato com os pastores",
            r"numero (dos )?pastor(es)?",
            r"telefone (dos )?pastor(es)?",
            r"secretario wilson",
            r"wilson martins",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_falar_pastores(texto_normalizado):
        resposta = (
            "Para falar diretamente com nossos pastores ou agendar uma visita pastoral, "
            "entre em contato com nossa secretaria:\n\n"
            "📞 *(48) 99828-4104*\n"
            "👤 *Secretário Presbítero Wilson Martins*\n\n"
            "Estaremos felizes em atendê-lo! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # 🎯 PRIORIDADE 2: Horários de cultos / programação da igreja
    def detectar_intencao_horarios_cultos(texto: str) -> bool:
        """
        Detecta perguntas sobre horários de cultos e programação da igreja.
        """
        texto = texto.lower().strip()
        
        padroes = [
            r"horarios? (de )?cultos?",
            r"horarios? (da )?igreja",
            r"quando (temos|são|sao|é|e) (os )?cultos?",
            r"qual (é|e) (o )?horario (do )?culto",
            r"programa(ç|c)ao (da )?igreja",
            r"programa(ç|c)ao dos cultos",
            r"cultos? (quando|horario)",
            r"que horas (é|e) (o )?culto",
            r"que dia (temos|são|sao) cultos?",
            r"agenda (da )?igreja",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_horarios_cultos(texto_normalizado):
        resposta = (
            "*Seguem nossos horários de cultos:*\n\n"
            "🌅 *Domingo*\n"
            "• Culto da Família: 09h\n"
            "• Culto de Celebração: 18h\n\n"
            "🌙 *Quarta-feira*\n"
            "• Culto de Oração e Palavra: 19h\n\n"
            "📍 *Local:* Rua das Flores, 123 - Canasvieiras\n\n"
            "Estamos esperando por você! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # 🎯 PRIORIDADE 3: Saber QUEM SÃO os pastores (informação, não contato)
    def detectar_intencao_pastores(texto: str) -> bool:
        """
        Detecta se o visitante está perguntando QUEM SÃO os pastores.
        Ignora contextos de contato direto (já tratados acima).
        """
        texto = texto.lower().strip()

        padroes_validos = [
            r"quem (é|são|e|sao) (os |o |as |a )?pastores?",
            r"quem (são|sao|é|e) (o |os |a |as )?pastor(es)?",
            r"qual (é|e|são|sao) (o |os |a |as )?pastor(es)?",
            r"quem é o pastor",
            r"quem são os líderes",
            r"pastores? da igreja",
            r"nome dos pastores",
            r"quem (são|sao) (os )?lideres?",
        ]

        padroes_ignorados = [
            r"pastor [a-z]",      # Ex: "pastor fabio" → não é pergunta
            r"pastora [a-z]",     # Ex: "pastora claudia" → não é pergunta
            r"falar com",         # Já tratado acima
            r"contato",           # Já tratado acima
            r"whatsapp",          # Já tratado acima
            r"agenda",            # Já tratado acima
            r"visita",            # Já tratado acima
            r"teste",
            r"não precisa responder",
            r"mensagem de teste",
        ]

        if any(re.search(p, texto) for p in padroes_ignorados):
            return False

        return any(re.search(p, texto) for p in padroes_validos)

    if detectar_intencao_pastores(texto_normalizado):
        resposta = (
            "Nossos pastores atuais são:\n"
            "- *Pr. Fábio Ferreira*\n"
            "- *Pra. Cláudia Ferreira*\n\n"
            "Você pode seguir o Pr. Fábio no Instagram: @prfabioferreirasoficial\n"
            "E a Pra. Cláudia em: @claudiaferreiras1"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": estado_atual.name}

    # 🎯 PRIORIDADE 4: Grupos de WhatsApp / GC
    def detectar_intencao_grupo_whatsapp(texto: str) -> bool:
        """
        Detecta interesse em entrar em grupos de WhatsApp ou GC.
        """
        texto = texto.lower().strip()
        
        padroes = [
            r"grupo (do )?whatsapp",
            r"entrar (no )?grupo",
            r"participar (do )?grupo",
            r"gc",
            r"grupo de comunh[aã]o",
            r"grupos? da igreja",
            r"como entro no grupo",
            r"link (do )?grupo",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_grupo_whatsapp(texto_normalizado):
        resposta = (
            "*Grupos de Comunhão (GC)* - _Pequenos encontros semanais nos lares!_\n\n"
            "Para entrar em um GC próximo a você:\n"
            "1️⃣ Nos informe seu bairro ou região\n"
            "2️⃣ Nossa equipe entrará em contato para conectar você ao grupo ideal\n\n"
            "Ou fale diretamente com nossa secretaria: *(48) 99828-4104*\n\n"
            "Queremos caminhar com você! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🔁 Fluxo normal de transições (menu numérico)
    # ==========================================================
    if proximo_estado:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta = obter_mensagem_estado(proximo_estado, visitor_name)
        atualizar_status(numero_normalizado, proximo_estado.value, origem=origem)
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": proximo_estado.name}

    # ==========================================================
    # 🤖 Fallback para IA (conhecimento treinado)
    # ==========================================================
    try:
        resposta_ia, confianca = ia_integracao.responder_pergunta(pergunta_usuario=texto_recebido)
        if resposta_ia and confianca > 0.2:
            enviar_mensagem_para_fila(numero_normalizado, resposta_ia, meta=_criar_meta())
            salvar_conversa(numero_normalizado, resposta_ia, tipo="enviada", sid=message_sid, origem=origem)
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value, origem=origem)
            return {"resposta": resposta_ia, "estado_atual": estado_atual.name, "proximo_estado": EstadoVisitante.INICIO.name}
    except Exception as e:
        logging.error(f"❌ Erro IA: {e}")

    # ==========================================================
    # ❌ Se nada funcionou: resposta padrão
    # ==========================================================
    visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
    resposta = f"Desculpe, {visitor_name}, não entendi sua resposta. Por favor, escolha uma das opções do menu:\n\n1️⃣ Já fiz batismo nas águas e quero me tornar membro\n2️⃣ Ainda não fiz batismo nas águas e quero me tornar membro\n3️⃣ Gostaria de receber orações\n4️⃣ Quero saber os horários dos cultos\n5️⃣ Entrar no grupo do WhatsApp\n6️⃣ Outro assunto"
    
    enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta())
    salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)

    return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": estado_atual.name}
