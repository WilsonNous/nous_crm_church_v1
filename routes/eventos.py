import logging, os, requests, time
from flask import request, jsonify
from database import (
    salvar_envio_evento, listar_envios_eventos,
    filtrar_visitantes_para_evento, get_db_connection
)

def register(app):
    # --- FILTRAR VISITANTES ---
    @app.route('/api/eventos/filtrar', methods=['POST'])
    def api_eventos_filtrar():
        try:
            data = request.json
            visitantes = filtrar_visitantes_para_evento(
                data_inicio=data.get("data_inicio"),
                data_fim=data.get("data_fim"),
                idade_min=data.get("idade_min"),
                idade_max=data.get("idade_max"),
                genero=data.get("genero")
            )
            return jsonify({"status": "success", "visitantes": visitantes}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/filtrar: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # --- ENVIAR CAMPANHA ---
    @app.route('/api/eventos/enviar', methods=['POST'])
    def api_eventos_enviar():
        try:
            data = request.json
            logging.info(f"📩 Dados recebidos para campanha: {data}")

            evento_nome = data.get("evento_nome")
            mensagem = data.get("mensagem")
            imagem_url = data.get("imagem_url")
            visitantes = data.get("visitantes")

            if not visitantes or not evento_nome or not mensagem:
                return jsonify({"status": "error", "message": "Dados incompletos para envio"}), 400

            ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
            ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
            ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")
            if not ZAPI_INSTANCE or not ZAPI_TOKEN or not ZAPI_CLIENT_TOKEN:
                logging.error("❌ Variáveis do Z-API não configuradas!")
                return jsonify({"status": "error", "message": "Configuração Z-API ausente"}), 500

            headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}
            enviados, falhas = [], []

            for v in visitantes:
                visitante_id = v.get("id")
                telefone = v.get("telefone")
                if not telefone:
                    falhas.append({"id": visitante_id, "motivo": "telefone ausente"})
                    continue

                telefone_envio = f"55{telefone}" if not telefone.startswith("55") else telefone
                try:
                    if imagem_url:
                        payload = {"phone": telefone_envio, "caption": mensagem, "image": imagem_url}
                        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
                    else:
                        payload = {"phone": telefone_envio, "message": mensagem}
                        url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

                    logging.info(f"➡️ Enviando para {telefone_envio} via {url}")
                    response = requests.post(url, json=payload, headers=headers, timeout=15)
                    status = "enviado" if response.ok else f"falha: {response.status_code}"

                    salvar_envio_evento(visitante_id, evento_nome, mensagem, imagem_url, status)
                    enviados.append({"id": visitante_id, "telefone": telefone_envio, "status": status})

                except Exception as e:
                    logging.error(f"❌ Erro ao enviar para {telefone_envio}: {e}")
                    salvar_envio_evento(visitante_id, evento_nome, mensagem, imagem_url, "erro")
                    falhas.append({"id": visitante_id, "telefone": telefone_envio, "status": "erro"})

                time.sleep(2)  # espaçamento entre mensagens

            return jsonify({"status": "success", "enviados": enviados, "falhas": falhas}), 200
        except Exception as e:
            logging.exception("Erro em /api/eventos/enviar")
            return jsonify({"status": "error", "message": str(e)}), 500

    # --- LISTAR ENVIOS ---
    @app.route('/api/eventos/envios', methods=['GET'])
    def api_eventos_envios():
        try:
            envios = listar_envios_eventos()
            return jsonify({"status": "success", "envios": envios}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/envios: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # --- REPROCESSAR ENVIOS COM ERRO ---
    @app.route('/api/eventos/reprocessar', methods=['POST'])
    def api_eventos_reprocessar():
        try:
            data = request.json
            evento_nome = data.get("evento_nome")

            if not evento_nome:
                return jsonify({"status": "error", "message": "Evento não informado"}), 400

            ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
            ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
            ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")
            headers = {"Client-Token": ZAPI_CLIENT_TOKEN, "Content-Type": "application/json"}

            enviados, falhas = [], []
            lote_size = 20

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ee.id as envio_id, v.id as visitante_id, v.telefone
                FROM eventos_envios ee
                JOIN visitantes v ON v.id = ee.visitante_id
                WHERE ee.evento_nome = %s AND ee.status = 'erro'
            """, (evento_nome,))
            pendentes = cursor.fetchall()

            total = len(pendentes)
            logging.info(f"🔄 Reprocessando {total} envios com erro para o evento {evento_nome}")

            for i in range(0, total, lote_size):
                lote = pendentes[i:i + lote_size]
                for p in lote:
                    visitante_id = p["visitante_id"]
                    telefone = p["telefone"]
                    telefone_envio = f"55{telefone}" if telefone and not telefone.startswith("55") else telefone

                    try:
                        cursor.execute("SELECT mensagem, imagem_url FROM eventos_envios WHERE id = %s", (p["envio_id"],))
                        row = cursor.fetchone()
                        mensagem = row["mensagem"]
                        imagem_url = row["imagem_url"]

                        if imagem_url:
                            payload = {"phone": telefone_envio, "caption": mensagem, "image": imagem_url}
                            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-image"
                        else:
                            payload = {"phone": telefone_envio, "message": mensagem}
                            url = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"

                        response = requests.post(url, json=payload, headers=headers, timeout=15)
                        status = "enviado" if response.ok else f"falha: {response.status_code}"

                        cursor.execute("UPDATE eventos_envios SET status = %s, data_envio = NOW() WHERE id = %s",
                                       (status, p["envio_id"]))
                        conn.commit()

                        enviados.append({"id": visitante_id, "telefone": telefone_envio, "status": status})
                    except Exception as e:
                        logging.error(f"Erro ao reprocessar visitante {visitante_id}: {e}")
                        falhas.append({"id": visitante_id, "telefone": telefone_envio, "status": "erro"})

                time.sleep(2)  # pausa entre lotes

            cursor.close()
            conn.close()

            return jsonify({"status": "success", "reprocessados": enviados, "falhas": falhas}), 200
        except Exception as e:
            logging.error(f"Erro em /api/eventos/reprocessar: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
