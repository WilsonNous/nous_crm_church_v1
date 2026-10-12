"""Fluxo persistente de oração. Não envia mensagens ao importar o módulo.

A rotina de expiração deve ser executada por agendador externo (Render Cron).
Os registros EM_ENVIO/INCERTO nunca são reenviados automaticamente.
"""
import logging
from datetime import datetime, timedelta, timezone
from contextlib import closing
from database import get_db_connection, atualizar_status, normalizar_para_envio
from constantes import EstadoVisitante
from servicos.fila_mensagens import enviar_mensagem_para_fila
from servicos.zapi_cliente import enviar_mensagem

INTERCESSORES = ('48984949640', '48999449961')


def _utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _conectar():
    conn = get_db_connection()
    if conn is None:
        raise RuntimeError('Banco indisponível; pedido de oração não pode ser registrado')
    return conn


def _registrar_interesse(cur, numero, origem):
    cur.execute('''INSERT INTO integra_interesses (telefone, origem, ultimo_interesse)
        VALUES (%s,%s,'PEDIDO_ORACAO') ON DUPLICATE KEY UPDATE
        ultimo_interesse=VALUES(ultimo_interesse), atualizado_utc=UTC_TIMESTAMP()''', (numero, origem))


def pedido_pendente(numero, origem='integra+'):
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, prazo_utc FROM integra_pedidos_oracao
                WHERE telefone=%s AND origem=%s AND estado='AGUARDANDO_MOTIVO'
                ORDER BY id DESC LIMIT 1''', (numero, origem))
            return cur.fetchone()


def iniciar_pedido(numero, nome, message_sid=None, origem='integra+'):
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT GET_LOCK(%s, 5) AS acquired', ('integra:oracao:' + numero,))
            if not cur.fetchone()['acquired']:
                raise RuntimeError('Não foi possível bloquear pedido simultâneo')
            try:
                if message_sid:
                    cur.execute('''SELECT id FROM integra_pedidos_oracao WHERE origem=%s AND sid_origem=%s LIMIT 1''', (origem, message_sid))
                    if cur.fetchone():
                        return {'resposta': None, 'estado_atual':'PEDIDO_ORACAO', 'proximo_estado':'AGUARDANDO_MOTIVO', 'duplicada': True}
                cur.execute('''SELECT id FROM integra_pedidos_oracao WHERE telefone=%s AND origem=%s
                    AND estado='AGUARDANDO_MOTIVO' LIMIT 1''', (numero, origem))
                existente = cur.fetchone()
                if not existente:
                    cur.execute('''INSERT INTO integra_pedidos_oracao
                        (telefone, origem, nome, sid_origem, prazo_utc) VALUES (%s,%s,%s,%s,%s)''',
                        (numero, origem, nome, message_sid or None, _utc()+timedelta(minutes=15)))
                _registrar_interesse(cur, numero, origem)
                conn.commit()
            finally:
                cur.execute('SELECT RELEASE_LOCK(%s)', ('integra:oracao:' + numero,))
    atualizar_status(numero, EstadoVisitante.PEDIDO_ORACAO.value, origem=origem)
    resposta = (f'{nome}, recebemos seu pedido de oração. 🙏\n'
                'Você gostaria de compartilhar o motivo? Pode responder aqui. '
                'Se preferir não informar, encaminharemos seu pedido à intercessão em até 15 minutos.')
    enviar_mensagem_para_fila(numero, resposta)
    return {'resposta': resposta, 'estado_atual':'PEDIDO_ORACAO', 'proximo_estado':'AGUARDANDO_MOTIVO'}


def receber_motivo(numero, texto, origem='integra+'):
    motivo = (texto or '').strip()
    if not motivo:
        return {'resposta':'Pode escrever o motivo do seu pedido de oração. 🙏'}
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, prazo_utc FROM integra_pedidos_oracao WHERE telefone=%s AND origem=%s
                AND estado='AGUARDANDO_MOTIVO' ORDER BY id DESC LIMIT 1 FOR UPDATE''', (numero, origem))
            pedido = cur.fetchone()
            if not pedido:
                conn.rollback()
                return None
            if pedido['prazo_utc'] <= _utc():
                conn.rollback()
                return None
            cur.execute('''UPDATE integra_pedidos_oracao SET motivo=%s, estado='PRONTO' WHERE id=%s''',
                        (motivo, pedido['id']))
            conn.commit()
    resposta = 'Recebemos o motivo do seu pedido. 🙏 Vamos encaminhá-lo à equipe de intercessão.'
    enviar_mensagem_para_fila(numero, resposta)
    return {'resposta':resposta, 'estado_atual':'PEDIDO_ORACAO', 'proximo_estado':'PRONTO'}


def processar_pendentes(limite=30):
    """Rodar em cron a cada minuto; não reenviar resultado incerto."""
    processados = 0
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id FROM integra_pedidos_oracao WHERE estado IN ('PRONTO','AGUARDANDO_MOTIVO')
                AND (estado='PRONTO' OR prazo_utc<=%s) ORDER BY id LIMIT %s''', (_utc(), limite))
            ids = [r['id'] for r in cur.fetchall()]
    for pedido_id in ids:
        with closing(_conectar()) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT GET_LOCK(%s, 0) AS acquired', ('integra:pedido:' + str(pedido_id),))
                if not cur.fetchone()['acquired']:
                    continue
                try:
                    cur.execute('''SELECT * FROM integra_pedidos_oracao WHERE id=%s FOR UPDATE''', (pedido_id,))
                    pedido = cur.fetchone()
                    if not pedido or pedido['estado'] not in ('PRONTO','AGUARDANDO_MOTIVO') or (pedido['estado']=='AGUARDANDO_MOTIVO' and pedido['prazo_utc']>_utc()):
                        conn.rollback()
                        continue
                    for numero in INTERCESSORES:
                        cur.execute('''INSERT IGNORE INTO integra_oracao_entregas(pedido_id,destinatario)
                            VALUES (%s,%s)''', (pedido_id, numero))
                    cur.execute("UPDATE integra_pedidos_oracao SET estado='ENCAMINHADO', encaminhado_utc=%s WHERE id=%s", (_utc(), pedido_id))
                    conn.commit()
                finally:
                    cur.execute('SELECT RELEASE_LOCK(%s)', ('integra:pedido:' + str(pedido_id),))
        processados += 1
    # A entrega é processada em uma etapa independente, com claim persistido antes da Z-API.
    with closing(_conectar()) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT e.id, e.destinatario, p.nome, p.telefone, p.motivo
                FROM integra_oracao_entregas e JOIN integra_pedidos_oracao p ON p.id=e.pedido_id
                WHERE e.estado='PENDENTE' ORDER BY e.id LIMIT %s''', (limite,))
            entregas = cur.fetchall()
    for entrega in entregas:
        with closing(_conectar()) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE integra_oracao_entregas SET estado='EM_ENVIO' WHERE id=%s AND estado='PENDENTE'", (entrega['id'],))
                if cur.rowcount != 1:
                    conn.rollback()
                    continue
                conn.commit()
        mensagem = (f"📖 Pedido de Oração\n\n🙏 Nome: {entrega['nome']}\n"
                    f"📱 Número: {entrega['telefone']}\n"
                    f"📝 Motivo: {entrega['motivo'] or 'Motivo não informado.'}")
        try:
            resultado = enviar_mensagem(normalizar_para_envio(entrega['destinatario']), mensagem)
            # Respostas negativas explícitas e exceções exigem conferência humana.
            confirmado = isinstance(resultado, dict) and resultado.get('success') is True
            estado = 'CONFIRMADO' if confirmado else 'INCERTO'
        except Exception:
            logging.exception('Entrega de oração incerta: id=%s', entrega['id'])
            estado = 'INCERTO'
        with closing(_conectar()) as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE integra_oracao_entregas SET estado=%s WHERE id=%s AND estado=\'EM_ENVIO\'', (estado, entrega['id']))
                conn.commit()
    return processados


if __name__ == '__main__':
    print('Pedidos preparados:', processar_pendentes())
