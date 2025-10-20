# ==============================================
# servicos/fila_mensagens.py
# ==============================================
# 📨 Fila unificada de envio de mensagens Z-API
# Usada pelo bot e pelas campanhas (envio sequencial)
# ==============================================

import time
import threading
import logging
from collections import deque
from servicos.zapi_cliente import enviar_mensagem

# Fila de mensagens em memória
fila_mensagens = deque()
lock = threading.Lock()

def processar_fila_mensagens():
    """Processa a fila de mensagens e envia sequencialmente via Z-API."""
    while True:
        with lock:
            if not fila_mensagens:
                break
            numero, mensagem, imagem_url = fila_mensagens.popleft()

        try:
            ok = enviar_mensagem(numero, mensagem, imagem_url)
            status = "✅" if ok else "❌"
            logging.info(f"{status} Fila → {numero} | {mensagem[:40]}...")
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem para {numero}: {e}")

        time.sleep(2)  # ⏱️ intervalo de 2s entre envios para evitar flood


def adicionar_na_fila(numero: str, mensagem: str, imagem_url: str = None):
    """
    Adiciona mensagem na fila e dispara o processamento
    se for a única mensagem.
    """
    with lock:
        fila_mensagens.append((numero, mensagem, imagem_url))
        if len(fila_mensagens) == 1:
            threading.Thread(target=processar_fila_mensagens, daemon=True).start()

# ✅ Alias para compatibilidade com versões antigas
enviar_mensagem_para_fila = adicionar_na_fila
