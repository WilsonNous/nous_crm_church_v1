# processamento_mensagens.py - CORREÇÃO COMPLETA COM JOVENS/ADOLESCENTES

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
    """
    logging.info(f"📥 Processando mensagem | Origem={origem} | Numero={numero}, SID={message_sid}, Mensagem={texto_recebido[:80]}... | is_webhook_reply={is_webhook_reply}")

    # Normalização
    numero_normalizado = numero.lstrip("55")
    texto_normalizado = normalizar_texto(texto_recebido)
    texto_original = texto_recebido.strip()
    
    # Salva mensagem recebida
    salvar_conversa(numero_normalizado, texto_recebido, tipo="recebida", sid=message_sid, origem=origem)

    # Estado atual do visitante
    estado_str = obter_estado_atual_do_banco(numero_normalizado)
    estado_atual = EstadoVisitante[estado_str] if estado_str in EstadoVisitante.__members__ else EstadoVisitante.INICIO

    logging.debug(f"📊 Estado atual no banco: {estado_str} → {estado_atual.name}")

    def _criar_meta(tipo="bot", is_reply_override: bool = None):
        if is_reply_override is not None:
            is_reply = is_reply_override
        else:
            is_reply = is_webhook_reply
        
        return {
            "origem": origem,
            "tipo": tipo,
            "is_reply": is_reply,
            "telefone_raw": numero_normalizado,
            "sid_origem": message_sid,
        }

    # ========== Palavra-chave de ministério ==========
    resposta_ministerio = detectar_palavra_chave_ministerio(texto_normalizado)
    if resposta_ministerio:
        enviar_mensagem_para_fila(numero_normalizado, resposta_ministerio, meta=_criar_meta(tipo="bot", is_reply_override=True))
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
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="manual", is_reply_override=False))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": "NOVO", "proximo_estado": "PEDIR_NOME"}

    # ========== Saudação ==========
    if detectar_saudacao(texto_normalizado):
        return processar_saudacao(numero_normalizado, message_sid, origem)

    # ========== Evento enviado ==========
    if estado_atual.name == "EVENTO_ENVIADO":
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        return processar_evento_enviado(numero_normalizado, visitor_name, message_sid, origem)

    # ========== Pedido de Oração ==========
    if texto_normalizado in ["3", "3.", "3️⃣", "pedido de oração", "pedido de oracao"]:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        texto_pedido_generico = "Pedido de oração solicitado pelo visitante."
        
        logging.info(f"🙏 Pedido de oração automático iniciado para {visitor_name} ({numero_normalizado})")

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
    # DETECÇÕES INTELIGENTES (ORDEM ESTRATÉGICA)
    # ==========================================================
    
    # ==========================================================
    # 🎯 PRIORIDADE 1: PASTORES
    # ==========================================================
    def detectar_intencao_pastores_unificado(texto: str) -> bool:
        texto = texto.lower().strip()
        
        padroes = [
            r"quem (é|são|e|sao) (os |o |as |a )?pastores?",
            r"quem (são|sao|é|e) (o |os |a |as )?pastor(es)?",
            r"qual (é|e|são|sao) (o |os |a |as )?pastor(es)?",
            r"quem é o pastor",
            r"quem são os líderes",
            r"pastores? da igreja",
            r"nome dos pastores",
            r"quem (são|sao) (os )?lideres?",
            r"fundadores da igreja",
            r"historia da igreja",
            r"falar (com|para) (o |a |os |as )?pastor(es)?",
            r"contato (com|dos|do|da) (o |a |os |as )?pastor(es)?",
            r"ligar (para|pros|pra) (o |a |os |as )?pastor(es)?",
            r"whatsapp (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"numero (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"telefone (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"como falo com (os |as )?pastor(es)?",
            r"como entro em contato com (os |as )?pastor(es)?",
            r"agenda (com|dos|do|da) (o |a |os |as )?pastor(es)?",
            r"agendar (com|uma visita com) (o |a |os |as )?pastor",
            r"marcar (com|uma visita com) (o |a |os |as )?pastor",
            r"marcar.*agenda.*pastor",
            r"quero.*falar.*pastor",
            r"preciso.*contato.*pastor",
            r"visita pastoral",
            r"visita (dos|do|da) (o |a |os |as )?pastor(es)?",
            r"receber visita pastoral",
            r"visita dos pastores",
            r"agendar.*pastor",
            r"secretario wilson",
            r"wilson martins",
            r"falar com a secretaria",
            r"contato da secretaria",
            r"ligar para a secretaria",
            r"whatsapp da secretaria",
            r"secretaria da igreja",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_pastores_unificado(texto_original):
        resposta = (
            "Nossos pastores atuais são:\n"
            "- *Pr. Fábio Ferreira*\n"
            "- *Pra. Cláudia Ferreira*\n\n"
            "Você pode seguir o Pr. Fábio no Instagram: @prfabioferreirasoficial\n"
            "E a Pra. Cláudia em: @claudiaferreiras1\n\n"
            "📅 *Para agendar uma visita pastoral ou falar diretamente:*\n"
            "📞 *(48) 99828-4104*\n"
            "👤 *Secretário Presbítero Wilson Martins*\n\n"
            "Estaremos felizes em atendê-lo! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 2: JOVENS E ADOLESCENTES (NOVO!)
    # ==========================================================
    def detectar_intencao_jovens(texto: str) -> bool:
        texto = texto.lower().strip()
        
        padroes = [
            r"adolescentes?",
            r"jovens?",
            r"juventude",
            r"atividade para (adolescentes?|jovens?)",
            r"tem (grupo|atividade) (de|para) (adolescentes?|jovens?)",
            r"culto (para|de) jovens",
            r"culto alive",
            r"gc (de|para) (adolescentes?|jovens?)",
            r"o que tem para (adolescentes?|jovens?)",
            r"programação (para|dos) (jovens|adolescentes)",
            r"grupo de jovens",
            r"grupo de adolescentes",
            r"tem atividade para jovem",
            r"tem atividade para adolescente",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_jovens(texto_original):
        resposta = (
            "Sim! Temos atividades incríveis para adolescentes e jovens! 🙏🎉\n\n"
            "*Atividades para Adolescentes e Jovens:*\n\n"
            "• *Culto Alive* - Aos sábados às 20h\n"
            "  Um culto especial com linguagem jovem, louvores contemporâneos e mensagens que conectam com a realidade dos adolescentes.\n\n"
            "• *Grupo de Adolescentes (GC)* - Encontros semanais\n"
            "  Um espaço para comunhão, amizade e crescimento espiritual.\n\n"
            "• *Acampamentos e Retiros* - Durante o ano\n"
            "  Momentos especiais de conexão com Deus e novos amigos.\n\n"
            "• *Escola Bíblica* - Aos domingos\n"
            "  Aprendizado da Palavra de forma dinâmica e interativa.\n\n"
            "📍 *Local:* Rod. José Carlos Daux, 17876 - Canasvieiras, Florianópolis/SC\n\n"
            "Venha conhecer! Traga seus amigos! 🎵🔥\n\n"
            '"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis." (1 Timóteo 4:12)'
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 3: HORÁRIOS DE CULTOS
    # ==========================================================
    def detectar_intencao_horarios_cultos(texto: str) -> bool:
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
            r"horario dos cultos",
            r"horários dos cultos",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_horarios_cultos(texto_original):
        resposta = (
            "*Seguem nossos horários de cultos:*\n\n"
            
            "[DOMINGO - 10h] *Culto Celebração da Vida*\n"
            "Um momento de adoração e comunhão para toda a família.\n"
            "\"Eu e a minha casa serviremos ao Senhor.\" (Josué 24:15)\n\n"
            
            "[DOMINGO - 19h] *Culto Celebração da Vida*\n"
            "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção.\n"
            "\"Eu e a minha casa serviremos ao Senhor.\" (Josué 24:15)\n\n"
            
            "[QUINTA-FEIRA - 20h] *Quinta Profética*\n"
            "Um encontro de fé para vivermos o sobrenatural de Deus.\n"
            "\"Tudo é possível ao que crê.\" (Marcos 9:23)\n\n"
            
            "[SÁBADO - 20h] *Culto Alive*\n"
            "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito!\n"
            "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" (1 Timóteo 4:12)\n\n"
            
            "[TERÇA-FEIRA - 21h30] *Culto de Oração*\n"
            "Um momento de intimidade com Deus, onde elevamos nossas petições e intercedemos uns pelos outros.\n"
            "\"Orai sem cessar.\" (1 Tessalonicenses 5:17)\n\n"
            
            "📍 *Local:* Rod. José Carlos Daux, 17876 - Canasvieiras, Florianópolis/SC\n\n"
            
            "Somos Uma Igreja Família, Vivendo os Propósitos de Deus!\n"
            "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" (Mateus 18:20)\n\n"
            
            "Gostaria de mais informações?"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 4: GRUPOS DE WHATSAPP
    # ==========================================================
    def detectar_intencao_grupo_whatsapp(texto: str) -> bool:
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

    if detectar_intencao_grupo_whatsapp(texto_original):
        resposta = (
            "*Grupos de Comunhão (GC)* - _Pequenos encontros semanais nos lares!_\n\n"
            "Para entrar em um GC próximo a você:\n"
            "1) Nos informe seu bairro ou região\n"
            "2) Nossa equipe entrará em contato para conectar você ao grupo ideal\n\n"
            "Ou fale diretamente com nossa secretaria: *(48) 99828-4104*\n\n"
            "Queremos caminhar com você! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 5: BATISMO / MEMBRO
    # ==========================================================
    def detectar_intencao_batismo_membro(texto: str) -> bool:
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

    if detectar_intencao_batismo_membro(texto_original):
        resposta = (
            "*Que bom que você deseja caminhar conosco!* 🙏\n\n"
            "Para se tornar membro da Mais de Cristo Canasvieiras:\n\n"
            "1) *Batismo nas águas* (se ainda não foi batizado)\n"
            "2) *Curso de Membros* (conheça nossa visão e valores)\n"
            "3) *Entrevista pastoral* (converse com nossos líderes)\n\n"
            "Para iniciar seu processo, responda:\n"
            "• Digite *1* se já foi batizado nas águas\n"
            "• Digite *2* se ainda não foi batizado\n\n"
            "Ou fale com nossa secretaria: *(48) 99828-4104*"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 6: LOCALIZAÇÃO
    # ==========================================================
    def detectar_intencao_localizacao(texto: str) -> bool:
        texto = texto.lower().strip()
        
        padroes = [
            r"onde fica a igreja",
            r"endereco da igreja",
            r"localização da igreja",
            r"como chegar na igreja",
            r"rua da igreja",
            r"bairro da igreja",
            r"canasvieiras igreja",
            r"igreja em canasvieiras",
            r"mapa da igreja",
            r"google maps igreja",
        ]
        
        return any(re.search(p, texto) for p in padroes)

    if detectar_intencao_localizacao(texto_original):
        resposta = (
            "*📍 Nossa Localização:*\n\n"
            "Rod. José Carlos Daux, 17876\n"
            "Canasvieiras - Florianópolis/SC\n"
            "CEP: 88050-401\n\n"
            "*🗺️ Como chegar:*\n"
            "• Google Maps: [clique aqui para abrir](https://maps.google.com/?q=HG2V%2BG58+Rod.+Jos%C3%A9+Carlos+Daux,+17876+-+Canasvieiras,+Florian%C3%B3polis+-+SC,+88050-401)\n"
            "• Estacionamento disponível no local\n\n"
            "Estamos te esperando! 🙏"
        )
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {
            "resposta": resposta,
            "estado_atual": estado_atual.name,
            "proximo_estado": estado_atual.name
        }

    # ==========================================================
    # 🎯 PRIORIDADE 7: OPÇÕES DO MENU (CORRIGIDO)
    # ==========================================================
    def detectar_opcao_menu(texto: str) -> str | None:
        texto = texto.strip()
        
        # ✅ APENAS números isolados (sem palavras extras)
        if texto in ["1", "2", "3", "4", "5", "6"]:
            return texto
        
        # ✅ Apenas números com pontuação ou emoji
        if texto in ["1.", "2.", "3.", "4.", "5.", "6.", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]:
            return texto[0]
        
        # ✅ Frases EXATAS (não parciais) - para evitar falsos positivos
        # Usa \b para bordas de palavra
        opcoes_exatas = {
            "1": [r"\bja fiz batismo\b", r"\bjá fiz batismo\b", r"\bbatizado\b", r"\bquero ser membro e ja fui batizado\b"],
            "2": [r"\bnao fiz batismo\b", r"\bnão fiz batismo\b", r"\bainda nao fui batizado\b", r"\bainda não fui batizado\b", r"\bquero ser membro mas nao sou batizado\b"],
            "3": [r"\bpedido de oração\b", r"\bpedido de oracao\b", r"\bquero oração\b", r"\bquero oracao\b", r"\borar por mim\b"],
            "4": [r"\bhorarios cultos\b", r"\bhorários cultos\b", r"\bquando tem culto\b", r"\bprogramação igreja\b"],
            "5": [r"\bgrupo whatsapp\b", r"\bentrar grupo\b", r"\bgc\b", r"\bgrupo de comunhão\b"],
            "6": [r"\boutro assunto\b", r"\boutro\b", r"\bnenhuma das opções\b", r"\bnão é isso\b"],
        }
        
        for opcao, padroes in opcoes_exatas.items():
            for padrao in padroes:
                if re.search(padrao, texto, re.IGNORECASE):
                    return opcao
        
        return None

    opcao_menu = detectar_opcao_menu(texto_normalizado)
    if opcao_menu:
        proximo_estado = obter_proximo_estado(estado_atual, opcao_menu)
        if proximo_estado:
            visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
            resposta = obter_mensagem_estado(proximo_estado, visitor_name)
            atualizar_status(numero_normalizado, proximo_estado.value, origem=origem)
            enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
            salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
            return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": proximo_estado.name}

    # ==========================================================
    # FLUXO NORMAL DE TRANSIÇÕES
    # ==========================================================
    proximo_estado = obter_proximo_estado(estado_atual, texto_normalizado)
    if proximo_estado:
        visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
        resposta = obter_mensagem_estado(proximo_estado, visitor_name)
        atualizar_status(numero_normalizado, proximo_estado.value, origem=origem)
        enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
        salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)
        return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": proximo_estado.name}

    # ==========================================================
    # 🤖 IA como camada inteligente
    # ==========================================================
    try:
        resposta_ia, confianca = ia_integracao.responder_pergunta(pergunta_usuario=texto_recebido)
        if resposta_ia and confianca > 0.3:
            enviar_mensagem_para_fila(numero_normalizado, resposta_ia, meta=_criar_meta(tipo="bot", is_reply_override=True))
            salvar_conversa(numero_normalizado, resposta_ia, tipo="enviada", sid=message_sid, origem=origem)
            atualizar_status(numero_normalizado, EstadoVisitante.INICIO.value, origem=origem)
            return {"resposta": resposta_ia, "estado_atual": estado_atual.name, "proximo_estado": EstadoVisitante.INICIO.name}
    except Exception as e:
        logging.error(f"❌ Erro IA: {e}")

    # ==========================================================
    # ❌ Fallback
    # ==========================================================
    visitor_name = obter_nome_do_visitante(numero_normalizado).split()[0]
    
    resposta = (
        f"Oi, {visitor_name}! 🙏 Ainda não tenho uma resposta pronta para isso, "
        f"mas quero te ajudar!\n\n"
        f"*Você pode:*\n"
        f"• Digitar *1* a *6* para escolher uma opção do menu\n"
        f"• Perguntar sobre *horários de culto*, *batismo*, *grupos* ou *nossos pastores*\n"
        f"• Ou falar diretamente com nossa secretaria: *(48) 99828-4104*\n\n"
        f"Como posso te ajudar hoje?"
    )
    
    enviar_mensagem_para_fila(numero_normalizado, resposta, meta=_criar_meta(tipo="bot", is_reply_override=True))
    salvar_conversa(numero_normalizado, resposta, tipo="enviada", sid=message_sid, origem=origem)

    return {"resposta": resposta, "estado_atual": estado_atual.name, "proximo_estado": estado_atual.name}
