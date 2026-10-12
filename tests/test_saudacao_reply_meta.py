"""Regressao: saudacao iniciada pelo visitante precisa preservar is_reply na fila."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_greeting_passes_webhook_reply_flag():
    tree = ast.parse((ROOT / "servicos/processamento_mensagens.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "processar_saudacao"]
    assert calls
    assert any(any(k.arg == "is_webhook_reply" and isinstance(k.value, ast.Name) and k.value.id == "is_webhook_reply" for k in call.keywords) for call in calls)


def test_greeting_enqueues_reply_metadata():
    tree = ast.parse((ROOT / "servicos/saudacoes.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "enviar_mensagem_para_fila"]
    assert calls
    assert any(any(k.arg == "meta" and isinstance(k.value, ast.Dict) and any(isinstance(key, ast.Constant) and key.value == "is_reply" for key in k.value.keys) for k in call.keywords) for call in calls)
