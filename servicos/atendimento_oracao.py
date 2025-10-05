import logging
from datetime import datetime
from constantes import EstadoVisitante
from database import normalizar_para_envio, atualizar_status, salvar_conversa
from servicos.zapi_cliente import enviar_mensagem
from servicos.fila_mensagens import enviar_mensagem_para_fila
from database import registrar_estatistica

# Lista de números que receberão os pedidos de oração
LISTA_INTERCESSORES = ['48984949649', '48999449961']


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
            logging.error(f"Erro ao enviar pedido de oração para {numero}: {e}")


def processar_pedido_oracao(numero: str, nome_visitante: str, texto_recebido: str, message_sid: str, origem: str = "integra+"):
    """
    Processa o pedido de oração do visitante:
    - envia aos intercessores
    - responde ao visitante
    - atualiza o status e estatísticas
    """
    try:
        # Registrar pedido de oração recebido
        salvar_conversa(numero, f"Pedido de oração: {texto_recebido}", tipo="recebida", sid=message_sid, origem=origem)

        # Enviar para os intercessores
        enviar_pedido_oracao(LISTA_INTERCESSORES, nome_visitante, numero, texto_recebido)

        # Mensagem de confirmação ao visitante
        resposta = (
            f"Seu pedido de oração foi recebido, {nome_visitante}. 🙏\n"
            f"Nossa equipe de intercessão já está orando por você. "
            f"Confiamos que Deus está ouvindo e agindo!"
        )

        # Atualizar status e registrar estatística
        atualizar_status(numero, EstadoVisitante.FIM.value, origem=origem)
        registrar_estatistica(numero, EstadoVisitante.PEDIDO_ORACAO.value, EstadoVisitante.FIM.value)

        # Enviar e salvar resposta
        enviar_mensagem_para_fila(numero, resposta)
        salvar_conversa(numero, resposta, tipo="enviada", sid=message_sid, origem=origem)

        logging.info(f"🙏 Pedido de oração processado para {numero}")

        # Reinicia o fluxo para voltar ao menu inicial depois do atendimento
        atualizar_status(numero, EstadoVisitante.INICIO.value, origem=origem)

        return {
            "resposta": resposta,
            "estado_atual": EstadoVisitante.PEDIDO_ORACAO.name,
            "proximo_estado": EstadoVisitante.FIM.name
        }

    except Exception as e:
        logging.error(f"Erro ao processar pedido de oração para {numero}: {e}")
        return {"erro": str(e)}
