"""Webhook Z-API: testes isolados, sem WhatsApp ou banco de dados."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
fake_bot = ModuleType("botmsg")
fake_bot.tratar_mensagem_webhook = Mock(return_value={"status": "success"})
fake_db = ModuleType("database")
fake_db.normalizar_para_recebimento = Mock(side_effect=lambda p: p)
fake_db.verificar_sid_existente = Mock(return_value=False)
fake_const = ModuleType("constantes")
fake_const.DEBUG = False
sys.modules.update({"botmsg": fake_bot, "database": fake_db, "constantes": fake_const})
spec = importlib.util.spec_from_file_location("webhooks_under_test", ROOT / "routes" / "webhooks.py")
webhooks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(webhooks)

def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    webhooks.register(app)
    fake_bot.tratar_mensagem_webhook.reset_mock()
    return app.test_client()

def sample():
    return {"phone": "5548999999999", "messageId": "test-001", "text": {"message": "Olá"}, "fromMe": False}

def test_missing_token_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("ZAPI_WEBHOOK_TOKEN", raising=False)
    response = client().post("/api/webhook-zapi", json=sample())
    assert response.status_code == 503
    fake_bot.tratar_mensagem_webhook.assert_not_called()

def test_missing_or_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("ZAPI_WEBHOOK_TOKEN", "segredo-forte")
    c = client()
    assert c.post("/api/webhook-zapi", json=sample()).status_code == 401
    assert c.post("/api/webhook-zapi", json=sample(), headers={"X-Webhook-Token": "incorreto"}).status_code == 401
    fake_bot.tratar_mensagem_webhook.assert_not_called()

def test_valid_token_dispatches_message(monkeypatch):
    monkeypatch.setenv("ZAPI_WEBHOOK_TOKEN", "segredo-forte")
    response = client().post("/api/webhook-zapi", json=sample(), headers={"X-Webhook-Token": "segredo-forte"})
    assert response.status_code == 200
    fake_bot.tratar_mensagem_webhook.assert_called_once()

def test_legacy_twilio_disabled():
    response = client().post("/api/webhook", json={"Body": "Olá"})
    assert response.status_code == 410
    fake_bot.tratar_mensagem_webhook.assert_not_called()
