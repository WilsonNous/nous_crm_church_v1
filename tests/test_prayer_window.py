"""Offline behavior checks for the fifteen-minute prayer window."""
import ast
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Cursor:
    def __init__(self, store):
        self.store = store
        self.current = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        if sql.startswith('SELECT id, prazo_utc FROM integra_pedidos_oracao'):
            self.current = self.store['pending']
        elif sql.startswith('UPDATE integra_pedidos_oracao SET motivo='):
            self.store['reason'] = params[0]
            self.store['state'] = 'PRONTO'
        else:
            raise AssertionError(sql)
    def fetchone(self): return self.current

class Connection:
    def __init__(self, store): self.store = store
    def cursor(self): return Cursor(self.store)
    def rollback(self): self.store['rollbacks'] += 1
    def commit(self): self.store['commits'] += 1
    def close(self): pass

class WindowTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 12, 12, 0)
        self.store = {'pending': None, 'reason': None, 'state': 'AGUARDANDO_MOTIVO', 'rollbacks': 0, 'commits': 0}
        self.outbox = []
        tree = ast.parse((ROOT / 'servicos/oracao_persistente.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'receber_motivo')
        scope = {'_conectar': lambda: Connection(self.store), '_utc': lambda: self.now,
                 'closing': closing, 'enviar_mensagem_para_fila': lambda *args: self.outbox.append(args)}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<prayer-window>', 'exec'), scope)
        self.receive = scope['receber_motivo']

    def test_reason_inside_window(self):
        self.store['pending'] = {'id': 1, 'prazo_utc': self.now + timedelta(seconds=1)}
        result = self.receive('48999999999', 'Pela familia')
        self.assertEqual(result['proximo_estado'], 'PRONTO')
        self.assertEqual(self.store['reason'], 'Pela familia')
        self.assertEqual(len(self.outbox), 1)

    def test_reason_exactly_at_deadline(self):
        self.store['pending'] = {'id': 1, 'prazo_utc': self.now}
        self.assertIsNone(self.receive('48999999999', 'Pela familia'))
        self.assertIsNone(self.store['reason'])
        self.assertEqual(len(self.outbox), 0)

    def test_reason_after_deadline(self):
        self.store['pending'] = {'id': 1, 'prazo_utc': self.now - timedelta(seconds=1)}
        self.assertIsNone(self.receive('48999999999', 'Pela familia'))
        self.assertEqual(self.store['rollbacks'], 1)

    def test_no_pending_request(self):
        self.assertIsNone(self.receive('48999999999', 'Pela familia'))
        self.assertEqual(len(self.outbox), 0)

if __name__ == '__main__':
    unittest.main()
