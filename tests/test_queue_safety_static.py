"""Offline regression checks for queue safety. No network or WhatsApp calls."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
QUEUE = (ROOT / "servicos" / "fila_mensagens.py").read_text(encoding="utf-8")
CTRL = (ROOT / "servicos" / "anti_spam_controller.py").read_text(encoding="utf-8")

class QueueSafetyTests(unittest.TestCase):
    def test_python_syntax(self):
        ast.parse(QUEUE)
        ast.parse(CTRL)

    def test_backlog_separate_from_daily_quota(self):
        tree = ast.parse(QUEUE)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "enfileirar_boas_vindas_com_limite")
        source = ast.get_source_segment(QUEUE, fn)
        self.assertIn("FILA_MAX_PENDING", source)
        self.assertNotIn("FILA_DAILY_LIMIT", source)

    def test_distributed_send_lock_and_recheck(self):
        self.assertIn("_lock_envio_proativo()", QUEUE)
        self.assertIn("_anti_spam._cache_ts = 0", QUEUE)
        self.assertIn("GET_LOCK", QUEUE)
        self.assertIn("RELEASE_LOCK", QUEUE)

    def test_ambiguous_provider_outcome_not_automatically_requeued(self):
        tree = ast.parse(QUEUE)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_processar_fila_worker")
        source = ast.get_source_segment(QUEUE, fn)
        self.assertIn("provider_attempted", source)
        self.assertIn("ENVIO_INCERTO", source)
        self.assertIn("if provider_attempted:", source)
        self.assertIn("persisted_success = _db_mark_success", source)

    def test_daily_attempts_include_failures(self):
        self.assertIn('limits["total_sent"] + limits["total_failed"] >= DAILY_LIMIT', CTRL)
        self.assertIn('ZoneInfo(\'America/Sao_Paulo\')', CTRL)

if __name__ == "__main__":
    unittest.main()
