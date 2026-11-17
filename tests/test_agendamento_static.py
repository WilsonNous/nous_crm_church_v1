"""Regressões estáticas do agendamento; não conecta ao banco nem envia WhatsApp."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AgendaStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routes = (ROOT / "routes/agendamentos.py").read_text(encoding="utf-8")
        cls.public = (ROOT / "templates/agendar_espacos.html").read_text(encoding="utf-8")
        cls.admin = (ROOT / "templates/admin_reservas.html").read_text(encoding="utf-8")
        cls.agenda = (ROOT / "templates/agenda_geral.html").read_text(encoding="utf-8")

    def test_conflict_predicate_for_creation_and_approval(self):
        self.assertGreaterEqual(self.routes.count("hora_inicio < %s AND hora_fim > %s"), 3)
        self.assertIn("status = 'aprovado'", self.routes)
        self.assertIn("FOR UPDATE", self.routes)

    def test_booking_validation_and_duplicate_prevention(self):
        self.assertIn("if fim <= inicio:", self.routes)
        self.assertIn("if data_res < date.today():", self.routes)
        self.assertIn('Esta reserva já foi registrada.', self.routes)
        self.assertIn("if (salvando) return;", self.public)

    def test_sql_time_formats_are_context_specific(self):
        admin_section = self.routes.split("def admin_reservas():", 1)[1].split("def agenda_geral():", 1)[0]
        self.assertIn("TIME_FORMAT(r.hora_inicio, '%H:%i')", admin_section)
        self.assertIn("DATE_FORMAT(r.data, '%d/%m/%Y')", admin_section)
        self.assertIn("TIME_FORMAT(hora_inicio, '%%H:%%i')", self.routes)

    def test_public_data_minimization_and_safe_dom(self):
        public_section = self.routes.split("def listar_reservas(", 1)[1].split("def nova_reserva(", 1)[0]
        self.assertNotIn("finalidade,", public_section)
        self.assertNotIn("nome,", public_section)
        self.assertIn("textContent", self.public)
        self.assertNotIn("innerHTML +=", self.public)

    def test_admin_auth_and_agenda_grouping(self):
        self.assertIn('localStorage.getItem("jwt_token")', self.admin)
        self.assertIn("res.ok", self.admin)
        self.assertIn("reservas|groupby('data')", self.agenda)


if __name__ == "__main__":
    unittest.main()
