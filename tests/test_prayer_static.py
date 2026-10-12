"""Testes offline sem conexão com MySQL ou WhatsApp real."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class PrayerStaticTests(unittest.TestCase):
    def test_python_parses(self):
        for path in ('servicos/oracao_persistente.py', 'servicos/processamento_mensagens.py'):
            ast.parse((ROOT / path).read_text(encoding='utf-8'), filename=path)

    def test_reason_before_greeting(self):
        source = (ROOT / 'servicos/processamento_mensagens.py').read_text(encoding='utf-8')
        self.assertLess(source.index('pedido_pendente(numero_normalizado'), source.index('detectar_saudacao(texto_normalizado)'))
        self.assertNotIn('numero.lstrip("55")', source)

    def test_no_automatic_retry_after_unknown(self):
        source = (ROOT / 'servicos/oracao_persistente.py').read_text(encoding='utf-8')
        self.assertIn("estado='EM_ENVIO'", source)
        self.assertIn("estado='PENDENTE'", source)
        self.assertIn("resultado.get('success') is True", source)

    def test_schema(self):
        schema = (ROOT / 'migrations/20261012_oracao_persistente.sql').read_text(encoding='utf-8')
        self.assertIn('UNIQUE KEY uq_pedido_destinatario', schema)
        self.assertIn('UNIQUE KEY uq_oracao_sid', schema)
        self.assertIn('integra_interesses', schema)

if __name__ == '__main__':
    unittest.main()
