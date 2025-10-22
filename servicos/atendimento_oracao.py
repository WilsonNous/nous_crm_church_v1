import logging
from datetime import datetime
from constantes import EstadoVisitante
from database import normalizar_para_envio, atualizar_status, salvar_conversa, registrar_estatistica
from servicos.zapi_cliente import enviar_mensagem
from servicos.fila_mensagens import enviar_mensagem_para_fila

# 📜 Lista de números dos intercessores
LISTA_INTERCESSORES = ['48984949640', '48999449961']


def enviar_pedido_oracao(lista_intercessores: list, nome_visitante: str, numero_visitante: str, texto_recebido: str):
    """
    Envia um pedido de oração para todos os intercessores cadastrados.
    """
    mensagem = (
        f"📖 Pedido de Oração\n\n"
        f"🙏 Nome: {nome_visitante}\n"
        f"📱 Número: {numero_visitante}\n"
        f"📝 Pedido: {texto_recebido}\n"
        f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    for numero in lista_intercessores:
        try:
            numero_normalizado_oracao = normalizar_para_envio(numero)
            enviar_mensagem(numero_normalizado_oracao, mensagem)
        except Exception as e:
            logging.error(f"❌ Erro ao enviar pedido de oração para {numero}: {e}")


def processar_pedido_oracao(numero: str, nome_visitante: str, texto_recebido: str, message_sid: str, origem: str = "integra+"):
    """
    Processa o pedido de oração do visitante:
    - Envia aos intercessores
    - Responde ao visitante
    - Atualiza o status e estatísticas
    """
    try:
        # 🕊️ Registrar o pedido no histórico
        salvar_conversa(numero, f"Pedido de oração: {texto_recebido}", tipo="recebida", sid=message_sid, origem=origem)

        # 📤 Enviar para o Ministério de Intercessão
        enviar_pedido_oracao(LISTA_INTERCESSORES, nome_visitante, numero, texto_recebido)

        # 💬 Mensagem personalizada ao visitante
        if texto_recebido.strip().lower() in ["pedido de oração solicitado pelo visitante.", "pedido de oracao solicitado pelo visitante."]:
            # Caso genérico (sem descrição)
            resposta = (
                f"Seu pedido de oração foi recebido, {nome_visitante}. 🙏\n"
                f"Nossa equipe de intercessão já está orando por você.\n"
                f"Confiamos que Deus está ouvindo e agindo!\n\n"
                f"Se desejar, compartilhe aqui o motivo específico do seu pedido 💬"
            )
        else:
            # Caso com texto específico
            resposta = (
                f"Amém, {nome_visitante}. 🙏\n"
                f"Seu pedido foi encaminhado à equipe de intercessão, que já está orando por essa causa.\n"
                f"Lembre-se: *Deus ouve e responde no tempo certo.* ⏳\n\n"
                f"Se quiser continuar conversando, estou aqui pra te ouvir. 💬"
            )

        # 🔄 Atualizar status e estatísticas
        atualizar_status(numero, EstadoVisitante.FIM.value, origem=origem)
        registrar_estatistica(numero, EstadoVisitante.PEDIDO_ORACAO.value, EstadoVisitante.FIM.value)

        # 📦 Enviar e registrar a resposta
        enviar_mensagem_para_fila(numero, resposta)
        salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

        logging.info(f"🙏 Pedido de oração processado com sucesso para {numero}")

        # 🔁 Reinicia o fluxo para retornar ao menu inicial
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)

        return {
            "resposta": resposta,
            "estado_atual": EstadoVisitante.PEDIDO_ORACAO.name,
            "proximo_estado": EstadoVisitante.FIM.name
        }

    except Exception as e:
        logging.error(f"❌ Erro ao processar pedido de oração para {numero}: {e}")
        return {"erro": str(e)}
