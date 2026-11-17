"""Integration tests against disposable MySQL; never touch production or WhatsApp."""
import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import patch

import pymysql
from flask import Flask

if os.getenv("AGENDA_TEST_DB") != "isolated_ci":
    raise unittest.SkipTest("Requires disposable CI database")

def connect():
    return pymysql.connect(
        host=os.environ["AGENDA_DB_HOST"], port=int(os.getenv("AGENDA_DB_PORT", "3306")),
        user=os.environ["AGENDA_DB_USER"], password=os.environ["AGENDA_DB_PASSWORD"],
        database=os.environ["AGENDA_DB_NAME"], autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, charset="utf8mb4",
    )

fake_db = types.ModuleType("database")
fake_db.get_db_connection = connect
fake_zapi = types.ModuleType("servicos.zapi_cliente")
fake_zapi.enviar_mensagem = lambda *a, **kw: {"success": True}
with patch.dict(sys.modules, {"database": fake_db, "servicos.zapi_cliente": fake_zapi}):
    spec = importlib.util.spec_from_file_location("agenda_mysql_test", "routes/agendamentos.py")
    agenda = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agenda)


class MySQLBookingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("DROP TABLE IF EXISTS reservas")
                c.execute("DROP TABLE IF EXISTS spaces")
                c.execute("CREATE TABLE spaces (id INT PRIMARY KEY, nome VARCHAR(120) NOT NULL) ENGINE=InnoDB")
                c.execute("""CREATE TABLE reservas (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    space_id INT NOT NULL, nome VARCHAR(150), telefone VARCHAR(30),
                    finalidade VARCHAR(500), data DATE NOT NULL,
                    hora_inicio TIME NOT NULL, hora_fim TIME NOT NULL,
                    status VARCHAR(20) NOT NULL, criado_em DATETIME,
                    INDEX ix_slot (space_id, data, status, hora_inicio, hora_fim),
                    FOREIGN KEY (space_id) REFERENCES spaces(id)
                ) ENGINE=InnoDB""")
                c.execute("INSERT INTO spaces (id,nome) VALUES (1,'Templo'),(2,'Cozinha')")
            conn.commit()

    def setUp(self):
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM reservas")
            conn.commit()
        app = Flask(__name__, template_folder="../templates")
        app.register_blueprint(agenda.bp_agenda)
        self.client = app.test_client()
        self.payload = dict(space_id=1, data="2099-11-20", hora_inicio="19:00",
                            hora_fim="20:00", nome="Pessoa CI", telefone="48999999999",
                            finalidade="Ensaio")

    def post(self, payload=None):
        return self.client.post("/api/reservas/nova", json=payload or self.payload)

    def test_admin_display_and_general_agenda(self):
        self.assertEqual(self.post().status_code, 200)
        a = self.client.get("/admin/reservas")
        self.assertEqual(a.status_code, 200, a.get_data(as_text=True))
        self.assertIn("20/11/2099", a.get_data(as_text=True))
        self.assertIn("19:00", a.get_data(as_text=True))
        g = self.client.get("/admin/agenda-geral")
        self.assertEqual(g.status_code, 200, g.get_data(as_text=True))
        self.assertIn("20/11/2099", g.get_data(as_text=True))

    def test_create_duplicate_and_conflict(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post().status_code, 409)
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM reservas")
                reservation_id = c.fetchone()["id"]
        self.assertEqual(self.client.post(f"/admin/reservas/alterar/{reservation_id}/aprovar").status_code, 200)
        self.assertEqual(self.post(dict(self.payload, nome="Outra pessoa")).status_code, 409)

    def test_approval_conflict_and_delete(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post(dict(self.payload, nome="Segunda pessoa")).status_code, 200)
        with connect() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM reservas ORDER BY id")
                ids = [r["id"] for r in c.fetchall()]
        self.assertEqual(self.client.post(f"/admin/reservas/alterar/{ids[0]}/aprovar").status_code, 200)
        self.assertEqual(self.client.post(f"/admin/reservas/alterar/{ids[1]}/aprovar").status_code, 409)
        self.assertEqual(self.client.post(f"/admin/reservas/excluir/{ids[1]}").status_code, 200)
        self.assertEqual(self.client.post(f"/admin/reservas/excluir/{ids[1]}").status_code, 404)

    def test_public_view_hides_personal_data(self):
        self.assertEqual(self.post().status_code, 200)
        response = self.client.get("/api/reservas/listar/1/2099-11-20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["reservas"]), 1)
        self.assertNotIn("nome", response.json["reservas"][0])
        self.assertNotIn("finalidade", response.json["reservas"][0])


if __name__ == "__main__":
    unittest.main()
