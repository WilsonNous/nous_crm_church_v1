"""Regressions for monitor logging; no DB or WhatsApp access."""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "routes" / "app_monitor.py"

class MonitorLoggingTests(unittest.TestCase):
    def test_module_compiles(self):
        compile(SOURCE.read_text(encoding="utf-8"), str(SOURCE), "exec")

    def test_logger_defined_before_route(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "log" for t in n.targets)]
        routes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "monitor_status"]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(len(routes), 1)
        self.assertLess(assignments[0].lineno, routes[0].lineno)

    def test_monitor_fallback_does_not_expose_raw_exception(self):
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def monitor_status():")
        end = source.index("\n@monitor_bp.route(", start + 1)
        body = source[start:end]
        self.assertIn('"message": "Não foi possível consultar as métricas do WhatsApp."', body)
        self.assertNotIn('"message": str(e)', body)

if __name__ == "__main__":
    unittest.main()
