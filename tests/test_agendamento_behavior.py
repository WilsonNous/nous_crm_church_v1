"""Offline Flask route tests: no MySQL connection and no WhatsApp sends."""
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

from flask import Flask

fake_db = types.ModuleType("database")
fake_db.get_db_connection = lambda: None
fake_service = types.ModuleType("servicos.zapi_cliente")
fake_service.enviar_mensagem = lambda *a, **k: (_ for _ in ()).throw(AssertionError("real WhatsApp must never be called"))

with patch.dict(sys.modules, {"database": fake_db, "servicos.zapi_cliente": fake_service}):
    spec = importlib.util.spec_from_file_location("agenda_under_test", "routes/agendamentos.py")
    agenda = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agenda)


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.queries = []

    def execute(self, sql, args=None):
        self.queries.append((sql, args))

    def fetchone(self):
        return self.rows.pop(0)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = FakeCursor(rows)
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        pass


class BookingBehaviorTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(agenda.bp_agenda)
        self.client = app.test_client()
        self.valid = {
            "space_id": 1, "data": "2099-11-20",
            "hora_inicio": "19:00", "hora_fim": "20:00",
            "nome": "Pessoa Teste", "telefone": "48999999999",
            "finalidade": "Ensaio"
        }

    def test_invalid_json(self):
        res = self.client.post("/api/reservas/nova", data="oops", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    def test_rejects_inverted_hours_without_database(self):
        payload = dict(self.valid, hora_fim="18:00")
        with patch.object(agenda, "get_db_connection", side_effect=AssertionError("no DB expected")):
            res = self.client.post("/api/reservas/nova", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_rejects_past_date_without_database(self):
        payload = dict(self.valid, data="2020-01-01")
        with patch.object(agenda, "get_db_connection", side_effect=AssertionError("no DB expected")):
            res = self.client.post("/api/reservas/nova", json=payload)
        self.assertEqual(res.status_code, 400)

    def test_approved_conflict_blocks_insert(self):
        conn = FakeConnection([{"id": 1}, {"qtd": 1}])
        with patch.object(agenda, "get_db_connection", return_value=conn):
            res = self.client.post("/api/reservas/nova", json=self.valid)
        self.assertEqual(res.status_code, 409)
        self.assertFalse(conn.committed)
        self.assertFalse(any("INSERT INTO reservas" in q for q, _ in conn.cursor_obj.queries))

    def test_new_booking_persists_pending(self):
        conn = FakeConnection([{"id": 1}, {"qtd": 0}, {"qtd": 0}, {"qtd": 0}])
        with patch.object(agenda, "get_db_connection", return_value=conn):
            res = self.client.post("/api/reservas/nova", json=self.valid)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(conn.committed)
        self.assertTrue(any("INSERT INTO reservas" in q for q, _ in conn.cursor_obj.queries))

    def test_duplicate_booking_blocked(self):
        conn = FakeConnection([{"id": 1}, {"qtd": 0}, {"qtd": 0}, {"qtd": 1}])
        with patch.object(agenda, "get_db_connection", return_value=conn):
            res = self.client.post("/api/reservas/nova", json=self.valid)
        self.assertEqual(res.status_code, 409)
        self.assertFalse(conn.committed)

    def test_approval_conflict_blocks_update_and_whatsapp(self):
        row = {
            "id": 7, "space_id": 1, "nome": "Teste",
            "telefone": "48999999999", "data": "2099-11-20",
            "status": "pendente", "hora_inicio": "19:00",
            "hora_fim": "20:00", "inicio_formatado": "19:00",
            "fim_formatado": "20:00"
        }
        conn = FakeConnection([{"space_id": 1}, row, {"qtd": 1}])
        with patch.object(agenda, "get_db_connection", return_value=conn):
            res = self.client.post("/admin/reservas/alterar/7/aprovar")
        self.assertEqual(res.status_code, 409)
        self.assertFalse(conn.committed)
        self.assertFalse(any("UPDATE reservas" in q for q, _ in conn.cursor_obj.queries))


if __name__ == "__main__":
    unittest.main()
