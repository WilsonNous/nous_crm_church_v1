"""Auditoria automatizada dos bloqueios de seguranca antes do merge."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_private_admin_pages_require_server_authentication():
    source = (ROOT / "crmlogic.py").read_text(encoding="utf-8")
    # Nao aceitar liberacao irrestrita de HTML administrativo.
    assert 'path.startswith("/admin/")):\n        return None' not in source

def test_twilio_webhook_checks_signature():
    source = (ROOT / "routes" / "webhooks.py").read_text(encoding="utf-8")
    assert "RequestValidator" in source and "X-Twilio-Signature" in source

def test_zapi_webhook_checks_secret():
    source = (ROOT / "routes" / "webhooks.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in source and "ZAPI_WEBHOOK_TOKEN" in source
