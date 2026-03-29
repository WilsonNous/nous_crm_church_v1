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

    # ==========================================================
    # 🔍 DETECÇÕES INTELIGENTES (ORDEM ESTRATÉGICA!)
    # ==========================================================
    
    # 🎯 PRIORIDADE 1: Falar com pastores / secretaria / agendar visita
    # ✅ Esta detecção deve vir ANTES de detectar_intencao_pastores
    def detectar_intencao_falar_pastores(texto: str) -> bool:
        """
        Detecta se o visitante quer entrar em contato direto com os pastores ou secretaria.
        ✅ Regex flexível para aceitar artigos e variações naturais.
        """
        texto = texto.lower().strip()
        
        padroes = [
            # Contato direto com pastores
            r"falar (com|para) (o |a |os |as )?pastor(es)?",
            r"contato (com|dos|do|da) (o |a |os |as )?pastor(es)?",
            r"ligar (para|pros|pra) (o |a |os |as )?pastor(es)?",
            r"whatsapp (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"numero (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"telefone (dos|do|da) (o |a |os |as )?pastor(es)?",
            
            # Agenda/visita pastoral (CORRIGIDO: aceita artigos entre palavras)
            r"agenda (com|dos|do|da) (o |a |os |as )?pastor(es)?",
            r"agendar (com|uma visita com) (o |a |os |as )?pastor",
            r"marcar (com|uma visita com) (o |a |os |as )?pastor",
            r"marcar.*agenda.*pastor",  # Flexível: "quero marcar uma agenda com os pastores"
            r"quero.*falar.*pastor",
            r"preciso.*contato.*pastor",
            
            # Visita pastoral
            r"visita pastoral",
            r"visita (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"receber visita pastoral",
            r"visita dos pastores",
            
            # Perguntas diretas
            r"como falo com (os |as )?pastor(es)?",
            r"como entro em contato com (os |as )?pastor(es)?",
            r"como agendar com (os |as )?pastor(es)?",
            
            # Secretaria / Wilson
            r"secretario wilson",
            r"wilson martins",
            r"falar com a secretaria",
            r"contato da secretaria",
            r"ligar para a secretaria",
            r"whatsapp da secretaria",
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
        ✅ Aceita variações naturais e perguntas indiretas.
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
            r"calendario (da )?igreja",
            r"eventos (da )?igreja",
            r"o que tem hoje na igreja",
            r"o que vai ter hoje",
            r"tem culto hoje",
            r"vai ter culto",
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
            r"marcar",            # Já tratado acima
            r"ligar",             # Já tratado acima
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
            r"quero estar no grupo",
            r"me add no grupo",
            r"grupo do whatsapp",
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

    # 🎯 PRIORIDADE 5: Batismo / Tornar-se membro
    def detectar_intencao_batismo_membro(texto: str) -> bool:
        """
        Detecta interesse em batismo ou tornar-se membro.
        """
        texto = texto.lower().strip()
        
        padroes = [
            r"batismo",
            r"batizar",
            r"mergulho",
            r"imersão",
            r"tornar membro",
            r"virar membro",
            r"ser membro",
            r"membership",
            r"como me tornar membro",
            r"quero ser membro",
            r"membro da igreja",
            r"o que preciso para ser membro",
            r"requisitos para membro",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_batismo_membro(texto_normalizado):
        resposta = (
            "*Que bom que você deseja caminhar conosco!*
