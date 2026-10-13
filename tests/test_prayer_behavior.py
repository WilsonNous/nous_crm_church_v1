"""Behavioral offline tests for late prayer complements. No MySQL or WhatsApp access."""
import ast
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Cursor:
    def __init__(self, store):
        self.store = store
        self.rowcount = 0
        self.lastrowid = 0
        self.current = None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params):
        if query.startswith('SELECT id FROM integra_pedidos_oracao'):
            self.current = {'id': 42} if self.store['exists'] else None
        elif query.startswith('SELECT id FROM integra_oracao_complementos'):
            self.current = {'id': 99} if (params[0], params[1]) in self.store['sid'] else None
        elif query.startswith('INSERT IGNORE INTO integra_oracao_complementos'):
            key = (params[0], params[1])
            self.rowcount = 0 if key in self.store['sid'] else 1
            if self.rowcount:
                self.store['sid'].add(key)
                self.lastrowid = 99
        elif query.startswith('INSERT IGNORE INTO integra_oracao_complemento_entregas'):
            self.store['deliveries'].add(tuple(params))
        else:
            raise AssertionError('Unexpected SQL: ' + query)
    def fetchone(self): return self.current

class Connection:
    def __init__(self, store): self.store = store
    def cursor(self): return Cursor(self.store)
    def commit(self): self.store['commits'] += 1
    def close(self): pass

class PrayerBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.store = {'exists': True, 'sid': set(), 'deliveries': set(), 'commits': 0}
        source = (ROOT / 'servicos/oracao_complementos.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'registrar')
        scope = {'_conectar': lambda: Connection(self.store), 'closing': closing,
                 'datetime': datetime, 'timezone': timezone,
                 'INTERCESSORES': ('111', '222')}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<offline-prayer>', 'exec'), scope)
        self.registrar = scope['registrar']

    def test_two_intercessors_once_for_duplicate_sid(self):
        self.assertTrue(self.registrar('48999999999', 'Saude', 'sid-1'))
        self.assertTrue(self.registrar('48999999999', 'Saude', 'sid-1'))
        self.assertEqual(self.store['deliveries'], {(99, '111'), (99, '222')})
        self.assertEqual(len(self.store['sid']), 1)

    def test_missing_sid_is_not_accepted(self):
        self.assertFalse(self.registrar('48999999999', 'Saude', None))
        self.assertFalse(self.store['deliveries'])

    def test_no_previous_prayer(self):
        self.store['exists'] = False
        self.assertFalse(self.registrar('48999999999', 'Saude', 'sid-2'))
        self.assertFalse(self.store['deliveries'])

if __name__ == '__main__':
    unittest.main()
