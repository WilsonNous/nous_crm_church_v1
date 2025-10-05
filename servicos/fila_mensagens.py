import time
import threading
import logging
from collections import deque
from servicos.zapi_cliente import enviar_mensagem

# Fila de mensagens em memória
fila_mensagens = deque()

def processar_fila_mensagens():
    """Processa a fila de mensagens e envia sequencialmente via Z-API"""
    while fila_mensagens:
        numero, mensagem = fila_mensagens.popleft()
        try:
            enviar_mensagem(numero, mensagem)
            time.sleep(2)  # evita flood, intervalo de 2s
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem para {numero}: {e}")

def adicionar_na_fila(numero: str, mensagem: str):
    """
    Adiciona mensagem na fila e dispara o processamento
    se for a única mensagem.
    """
    fila_mensagens.append((numero, mensagem))
    if len(fila_mensagens) == 1:
        threading.Thread(target=processar_fila_mensagens).start()

# ✅ Alias para compatibilidade com versões antigas
enviar_mensagem_para_fila = adicionar_na_fila
