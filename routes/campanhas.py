# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Integra-se com database.py (PyMySQL)
# ================================================

from concurrent.futures import ThreadPoolExecutor
import requests
import logging
import config
import database
from flask import request, jsonify
from datetime import datetime

def register(app):

    # ------------------------------------------------
    # 🔍 1. Filtro de Visitantes
    # ------------------------------------------------
    @app.route('/api/visitantes/filtro', methods=['POST'])
    def filtrar_visitantes():
        try:
            filtros = request.get_json()
            data_inicio = filtros.get("dataInicio")
            data_fim = filtros.get("dataFim")
            idade_min = filtros.get("idadeMin")
            idade_max = filtros.get("idadeMax")
            genero = filtros.get("genero")

            visitantes = database.filtrar_visitantes_para_evento(
                data_inicio, data_fim, idade_min, idade_max, genero
            )

            resultado = []
            for v in visitantes:
                idade = None
                if v.get("data_nascimento"):
                    nasc = v["data_nascimento"]
                    if isinstance(nasc, datetime):
                        idade = datetime.now().year - nasc.year - (
                            (datetime.now().month, datetime.now().day) < (nasc.month, nasc.day)
                        )

                resultado.append({
                    "id": v["id"],
                    "nome": v["nome"],
                    "telefone": v["telefone"],
                    "genero": v["genero"],
                    "idade": idade,
                    "data_cadastro": v["data_cadastro"].strftime("%d/%m/%Y") if v.get("data_cadastro") else "-"
                })

            return jsonify({"visitantes": resultado}), 200

        except Exception as e:
            logging.exception(f"❌ Erro ao filtrar visitantes: {e}")
            return jsonify({"error": "Erro ao filtrar visitantes"}), 500


    # ------------------------------------------------
    # 📢 2. Enviar Campanha
    # ------------------------------------------------
    @app.route('/api/campanhas/enviar', methods=['POST'])
    def enviar_campanha():
        try:
            data = request.get_json() or {}
            nome_evento = data.get("nome_evento")
            mensagem = data.get("mensagem")
            imagem = data.get("imagem")
    
            data_inicio = data.get("dataInicio")
            data_fim = data.get("dataFim")
            idade_min = data.get("idadeMin")
            idade_max = data.get("idadeMax")
            genero = data.get("genero")
    
            visitantes = database.filtrar_visitantes_para_evento(
                data_inicio=data_inicio,
                data_fim=data_fim,
                idade_min=idade_min,
                idade_max=idade_max,
                genero=genero
            )
    
            if not visitantes:
                return jsonify({"message": "Nenhum visitante encontrado para envio."}), 200
    
            zapi_base = config.ZAPI_BASE_URL
            zapi_instance = config.ZAPI_INSTANCE
            zapi_token = config.ZAPI_CLIENT_TOKEN
            headers = {"Client-Token": zapi_token, "Content-Type": "application/json"}
    
            enviados, falhas = 0, 0
    
            # ======================================================
            # 🔹 Função interna de envio individual
            # ======================================================
            def processar_envio(v):
                visitante_id = v["id"]
                telefone = v.get("telefone")
                nome = v.get("nome")
    
                # registra como pendente
                database.salvar_envio_evento(
                    visitante_id=visitante_id,
                    evento_nome=nome_evento,
                    mensagem=mensagem,
                    imagem_url=imagem,
                    status="pendente",
                    origem="integra+"
                )
    
                if not telefone:
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    logging.warning(f"⚠️ Sem telefone: {nome}")
                    return ("falha", telefone)
    
                try:
                    # Define tipo de mensagem
                    if imagem:
                        url = f"{zapi_base}/message/sendImage/{zapi_instance}"
                        payload = {"phone": telefone, "message": mensagem, "image": imagem}
                    else:
                        url = f"{zapi_base}/message/sendText/{zapi_instance}"
                        payload = {"phone": telefone, "message": mensagem}
    
                    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    
                    if resp.status_code == 200:
                        database.atualizar_status_envio_evento(visitante_id, nome_evento, "enviado")
                        logging.info(f"✅ Enviado: {telefone} ({nome})")
                        return ("enviado", telefone)
                    else:
                        database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                        logging.warning(f"⚠️ Falha {telefone}: {resp.status_code} - {resp.text}")
                        return ("falha", telefone)
    
                except Exception as e:
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    logging.error(f"❌ Erro Z-API {telefone}: {e}")
                    return ("falha", telefone)
    
            # ======================================================
            # 🚀 ThreadPoolExecutor para envios simultâneos
            # ======================================================
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(processar_envio, visitantes))
    
            # contagem final
            enviados = sum(1 for r, _ in results if r == "enviado")
            falhas = sum(1 for r, _ in results if r == "falha")
    
            logging.info(f"📢 Campanha '{nome_evento}' finalizada → {enviados} enviados, {falhas} falhas.")
            return jsonify({
                "message": f"📢 Campanha '{nome_evento}' concluída com {enviados} enviados e {falhas} falhas.",
                "enviados": enviados,
                "falhas": falhas
            }), 200
    
        except Exception as e:
            logging.exception(f"Erro geral ao enviar campanha: {e}")
            return jsonify({"error": "Erro ao enviar campanha"}), 500


    # ------------------------------------------------
    # 🔁 3. Reprocessar Falhas
    # ------------------------------------------------
    @app.route('/api/campanhas/reprocessar', methods=['POST'])
    def reprocessar_falhas():
        try:
            envios = database.listar_envios_eventos(limit=200)
            falhas = [e for e in envios if e["status"] == "falha"]
            reprocessados = 0

            for f in falhas:
                ok = database.salvar_envio_evento(
                    visitante_id=f["id"],
                    evento_nome=f["evento_nome"],
                    mensagem=f["mensagem"],
                    imagem_url=f["imagem_url"],
                    status="reprocessado",
                    origem=f.get("origem", "integra+")
                )
                if ok:
                    reprocessados += 1

            return jsonify({
                "message": f"🔄 {reprocessados} falhas reprocessadas com sucesso."
            }), 200

        except Exception as e:
            logging.exception(f"Erro ao reprocessar falhas: {e}")
            return jsonify({"error": "Falha ao reprocessar"}), 500


    # ------------------------------------------------
    # 📊 4. Status de Campanhas (Resumo Agrupado)
    # ------------------------------------------------
    @app.route('/api/campanhas/status', methods=['GET'])
    def status_campanhas():
        try:
            campanhas = database.obter_resumo_campanhas(limit=100)
            if not campanhas:
                return jsonify({"status": []}), 200
    
            resultado = []
            for c in campanhas:
                resultado.append({
                    "nome_evento": c["evento_nome"],
                    "data_envio": c["ultima_data"].strftime("%d/%m/%Y %H:%M") if c.get("ultima_data") else "-",
                    "enviados": c.get("enviados", 0),
                    "falhas": c.get("falhas", 0),
                    "pendentes": c.get("pendentes", 0),
                    "status": (
                        "✅ Concluída" if c["falhas"] == 0 and c["pendentes"] == 0
                        else "⚠️ Parcial"
                    )
                })
    
            return jsonify({"status": resultado}), 200
    
        except Exception as e:
            logging.exception(f"Erro ao obter status de campanhas: {e}")
            return jsonify({"error": "Falha ao carregar status"}), 500


    # ------------------------------------------------
    # 🧹 5. Limpar histórico de campanhas
    # ------------------------------------------------
    @app.route('/api/campanhas/limpar', methods=['POST'])
    def limpar_campanhas():
        try:
            total = database.limpar_envios_eventos()
            logging.info(f"🧹 {total} registros de campanhas apagados com sucesso.")
            return jsonify({
                "message": f"🧹 Histórico limpo ({total} registros removidos)."
            }), 200
        except Exception as e:
            logging.exception(f"Erro ao limpar histórico: {e}")
            return jsonify({"error": "Falha ao limpar histórico"}), 500

