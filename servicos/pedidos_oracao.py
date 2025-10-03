import logging
from datetime import datetime
from database import normalizar_para_envio
from servicos.zapi_cliente import enviar_mensagem

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

