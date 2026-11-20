"""Unit checks for MySQL TLS configuration; no network or credentials required."""
import os
import ssl
import unittest
from unittest.mock import MagicMock, patch
import database


class EnzonicTLSConnectionTests(unittest.TestCase):
    @patch.dict(os.environ, {
        "MYSQL_HOST": "example.invalid",
        "MYSQL_USER": "test",
        "MYSQL_PASSWORD": "test",
        "MYSQL_DB": "main",
        "MYSQL_PORT": "3306",
        "MYSQL_SSL_REQUIRED": "1",
    }, clear=True)
    @patch("database.pymysql.connect")
    def test_verified_tls_and_cipher(self, connect):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = {
            "Variable_name": "Ssl_cipher", "Value": "TLS_AES_256_GCM_SHA384"
        }
        connect.return_value = conn
        self.assertIs(database.get_db_connection(), conn)
        context = connect.call_args.kwargs["ssl"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    @patch.dict(os.environ, {
        "MYSQL_HOST": "example.invalid",
        "MYSQL_SSL_REQUIRED": "1",
    }, clear=True)
    @patch("database.pymysql.connect")
    def test_rejects_unencrypted_session(self, connect):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = {
            "Variable_name": "Ssl_cipher", "Value": ""
        }
        connect.return_value = conn
        self.assertIsNone(database.get_db_connection())
        conn.close.assert_called_once()

    @patch.dict(os.environ, {"MYSQL_SSL_REQUIRED": "0"}, clear=True)
    @patch("database.pymysql.connect")
    def test_legacy_mode_does_not_force_tls(self, connect):
        self.assertIs(database.get_db_connection(), connect.return_value)
        self.assertNotIn("ssl", connect.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
