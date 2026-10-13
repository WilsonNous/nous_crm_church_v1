"""Armazena complementos tardios sem reenviar o pedido original."""
from contextlib import closing
from datetime import datetime, timezone
from servicos.oracao_persistente import _conectar, INTERCESSORES


def registrar(numero, texto, sid=None, origem='integra+'):
    if not sid or not (texto or '').strip():
        return False
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
            cur.execute("INSERT IGNORE INTO integra_oracao_complementos (pedido_id,sid_origem,texto,criado_utc) VALUES (%s,%s,%s,%s)", (pedido['id'],sid,texto,datetime.now(timezone.utc).replace(tzinfo=None)))
            if cur.rowcount == 0:
                return True
            complemento = cur.lastrowid
            for destino in INTERCESSORES:
                cur.execute("INSERT IGNORE INTO integra_oracao_complemento_entregas (complemento_id,destinatario) VALUES (%s,%s)", (complemento,destino))
            conn.commit()
            return True


def processar(limite=30):
    from servicos.zapi_cliente import enviar_mensagem
    from database import normalizar_para_envio
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT e.id, e.destinatario, c.texto, p.nome, p.telefone
                FROM integra_oracao_complemento_entregas e
                JOIN integra_oracao_complementos c ON c.id=e.complemento_id
                JOIN integra_pedidos_oracao p ON p.id=c.pedido_id
                WHERE e.estado='PENDENTE' ORDER BY e.id LIMIT %s""", (limite,))
            entregas = cur.fetchall()
    for entrega in entregas:
        with closing(_conectar()) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE integra_oracao_complemento_entregas SET estado='EM_ENVIO' WHERE id=%s AND estado='PENDENTE'", (entrega['id'],))
                if cur.rowcount != 1:
                    conn.rollback()
                    continue
                conn.commit()
        mensagem = (f"🙏 Complemento de oração\nNome: {entrega['nome']}\n"
                    f"Telefone: {entrega['telefone']}\nMotivo: {entrega['texto']}")
        try:
            resultado = enviar_mensagem(normalizar_para_envio(entrega['destinatario']), mensagem, sem_retry=True)
            estado = 'CONFIRMADO' if isinstance(resultado, dict) and resultado.get('success') is True else 'INCERTO'
        except Exception:
            estado = 'INCERTO'
        with closing(_conectar()) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE integra_oracao_complemento_entregas SET estado=%s WHERE id=%s AND estado='EM_ENVIO'", (estado, entrega['id']))
                conn.commit()
