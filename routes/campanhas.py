# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Integra-se com database.py (PyMySQL)
# ================================================

import logging
from flask import request, jsonify
from datetime import datetime
import database

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
            data = request.get_json()
            nome_evento = data.get("nome_evento")
            mensagem = data.get("mensagem")
            imagem = data.get("imagem")

            visitantes = database.filtrar_visitantes_para_evento()
            enviados = 0
            falhas = 0

            for v in visitantes:
                ok = database.salvar_envio_evento(
                    visitante_id=v["id"],
                    evento_nome=nome_evento,
                    mensagem=mensagem,
                    imagem_url=imagem,
                    status="pendente",
                    origem="integra+"
                )
                if ok:
                    enviados += 1
                else:
                    falhas += 1

            logging.info(f"📢 Campanha '{nome_evento}' registrada: {enviados} enviados, {falhas} falhas.")
            return jsonify({
                "message": f"Campanha '{nome_evento}' enviada com sucesso!",
                "enviados": enviados,
                "falhas": falhas
            }), 200

        except Exception as e:
            logging.exception(f"Erro ao enviar campanha: {e}")
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
    # 🧹 5. Limpar Histórico de Campanhas
    # ------------------------------------------------
    @app.route('/api/campanhas/limpar', methods=['DELETE'])
    def limpar_campanhas():
        try:
            total = database.limpar_envios_eventos()
            logging.info(f"🧹 {total} registros de campanhas removidos do histórico.")
            return jsonify({"message": f"🧹 {total} registros removidos."}), 200
        except Exception as e:
            logging.exception(f"Erro ao limpar histórico: {e}")
            return jsonify({"error": "Erro ao limpar histórico"}), 500
