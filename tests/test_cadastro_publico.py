"""Testes isolados do cadastro publico sem acesso ao banco ou WhatsApp."""
import importlib
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from flask import Flask

fake_db = ModuleType("database")
fake_db.salvar_visitante = lambda **kwargs: False
fake_db.visitante_existe = lambda phone: False
fake_db.normalizar_para_recebimento = lambda phone: phone
sys.modules["database"] = fake_db
module = importlib.import_module("routes.cadastro_publico")

def client():
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / "templates"))
    app.register_blueprint(module.cadastro_publico_bp)
    app.config["TESTING"] = True
    module._tentativas.clear()
    return app.test_client()

def payload(**overrides):
    data = {
        "name": "Visitante de Teste", "phone": "48999999999",
        "city": "Florianópolis", "birthdate": "1990-06-15",
        "gender": "feminino", "maritalStatus": "solteiro",
    }
    data.update(overrides)
    return data

def test_page_loads():
    assert client().get("/cadastro-visitante").status_code == 200

def test_required_fields():
    for key in ("name", "phone", "city", "birthdate", "gender", "maritalStatus"):
        data = payload()
        data.pop(key)
        with patch.object(module, "normalizar_para_recebimento", return_value="5548999999999"):
            response = client().post("/api/public/visitantes", json=data)
        assert response.status_code == 400, key

def test_invalid_birthdate():
    response = client().post("/api/public/visitantes", json=payload(birthdate="2099-01-01"))
    assert response.status_code == 400

def test_valid_submission_saves_demographics():
    with patch.object(module, "normalizar_para_recebimento", return_value="5548999999999"), \
         patch.object(module, "visitante_existe", return_value=False), \
         patch.object(module, "salvar_visitante", return_value=True) as save:
        response = client().post("/api/public/visitantes", json=payload())
    assert response.status_code == 201
    assert save.call_args.kwargs["cidade"] == "Florianópolis"
    assert save.call_args.kwargs["genero"] == "feminino"
    assert save.call_args.kwargs["estado_civil"] == "solteiro"
    assert save.call_args.kwargs["data_nascimento"] == "1990-06-15"
    assert save.call_args.kwargs["origem"] == "cadastro_publico"

def test_duplicate_does_not_disclose_number():
    with patch.object(module, "normalizar_para_recebimento", return_value="5548999999999"), \
         patch.object(module, "visitante_existe", return_value=True):
        response = client().post("/api/public/visitantes", json=payload())
    assert response.status_code == 409
    assert "já está cadastrado" not in response.get_json()["error"]

def test_honeypot_does_not_write():
    with patch.object(module, "salvar_visitante") as save:
        response = client().post("/api/public/visitantes", json=payload(website="spam"))
    assert response.status_code == 200
    save.assert_not_called()

def test_rate_limit():
    c = client()
    for _ in range(8):
        c.post("/api/public/visitantes", json=payload(name="X"))
    assert c.post("/api/public/visitantes", json=payload()).status_code == 429


def test_invalid_phone_and_email():
    c = client()
    assert c.post("/api/public/visitantes", json=payload(phone="123")).status_code == 400
    assert c.post("/api/public/visitantes", json=payload(email="invalido")).status_code == 400

def test_invalid_date_and_unrecognized_choices():
    c = client()
    for birthday in ("2020-02-30", "1800-01-01", "texto"):
        assert c.post("/api/public/visitantes", json=payload(birthdate=birthday)).status_code == 400
    assert c.post("/api/public/visitantes", json=payload(gender="invalido")).status_code == 400
    assert c.post("/api/public/visitantes", json=payload(maritalStatus="invalido")).status_code == 400

def test_missing_json_and_oversized_body():
    c = client()
    assert c.post("/api/public/visitantes", data="texto", content_type="text/plain").status_code == 415
    assert c.post("/api/public/visitantes", data="x" * 12001, content_type="application/json").status_code == 413

def test_no_write_on_invalid_submission():
    with patch.object(module, "salvar_visitante") as save:
        response = client().post("/api/public/visitantes", json=payload(city=""))
    assert response.status_code == 400
    save.assert_not_called()

def test_optional_privacy_choices():
    with patch.object(module, "normalizar_para_recebimento", return_value="5548999999999"), \
         patch.object(module, "visitante_existe", return_value=False), \
         patch.object(module, "salvar_visitante", return_value=True) as save:
        response = client().post("/api/public/visitantes", json=payload(gender="nao_informado", maritalStatus="nao_informado"))
    assert response.status_code == 201
    assert save.call_args.kwargs["genero"] == "nao_informado"
    assert save.call_args.kwargs["estado_civil"] == "nao_informado"


def test_interest_in_membership_does_not_create_member():
    with patch.object(module, "normalizar_para_recebimento", return_value="5548999999999"), \
         patch.object(module, "visitante_existe", return_value=False), \
         patch.object(module, "salvar_visitante", return_value=True) as save:
        response = client().post("/api/public/visitantes", json=payload(membership=True))
    assert response.status_code == 201
    assert save.call_args.kwargs["membro"] is False
