"""Armazena complementos tardios sem reenviar o pedido original."""
from contextlib import closing
from datetime import datetime, timezone
from servicos.oracao_persistente import _conectar, INTERCESSORES


def registrar(numero, texto, sid=None, origem='integra+'):
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM integra_pedidos_oracao WHERE telefone=%s AND origem=%s AND estado='ENCAMINHADO' ORDER BY id DESC LIMIT 1", (numero, origem))
            pedido = cur.fetchone()
            if not pedido:
                return False
            if sid:
                cur.execute("SELECT id FROM integra_oracao_complementos WHERE pedido_id=%s AND sid_origem=%s", (pedido['id'], sid))
                if cur.fetchone():
                    return True
            cur.execute("INSERT INTO integra_oracao_complementos (pedido_id,sid_origem,texto,criado_utc) VALUES (%s,%s,%s,%s)", (pedido['id'],sid,texto,datetime.now(timezone.utc).replace(tzinfo=None)))
            complemento = cur.lastrowid
            for destino in INTERCESSORES:
                cur.execute("INSERT IGNORE INTO integra_oracao_complemento_entregas (complemento_id,destinatario) VALUES (%s,%s)", (complemento,destino))
            conn.commit()
            return True
