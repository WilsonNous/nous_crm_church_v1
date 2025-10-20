# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Envio 100% texto (sem imagem) para máxima entregabilidade
# ================================================

import logging
from flask import request, jsonify
from datetime import datetime
import database
from database import salvar_conversa
from servicos.fila_mensagens import adicionar_na_fila


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
    # 📢 2. Enviar Campanha (modo texto puro)
    # ------------------------------------------------
    @app.route('/api/campanhas/enviar', methods=['POST'])
    def enviar_campanha():
        try:
            data = request.get_json() or {}
            nome_evento = data.get("nome_evento")
            mensagem = data.get("mensagem")
            
            # 🔹 Ignora imagem — envio sempre em modo texto puro
            imagem = None  

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

            enviados, falhas = 0, 0

            for v in visitantes:
                visitante_id = v["id"]
                telefone = v.get("telefone")
                nome = v.get("nome")

                try:
                    # Registra como pendente
                    database.salvar_envio_evento(
                        visitante_id=visitante_id,
                        evento_nome=nome_evento,
                        mensagem=mensagem,
                        imagem_url=None,  # garante que não salva mídia
                        status="pendente",
                        origem="campanha"
                    )

                    if not telefone:
                        database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                        logging.warning(f"⚠️ Visitante sem telefone: {nome}")
                        falhas += 1
                        continue

                    # 🔹 Envia apenas texto via fila
                    adicionar_na_fila(telefone, mensagem)

                    # 💬 Salva no histórico de conversas
                    salvar_conversa(
                        numero=telefone,
                        mensagem=mensagem,
                        tipo="enviada",
                        sid=None,
                        origem="campanha"
                    )

                    # 🔄 Atualiza status do envio no banco
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "enviado")
                    logging.info(f"📬 Visitante {nome} adicionado à fila de envio.")
                    enviados += 1

                except Exception as e:
                    falhas += 1
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    logging.error(f"❌ Erro ao processar visitante {nome}: {e}")

            logging.info(f"📢 Campanha '{nome_evento}' concluída → {enviados} enviados, {falhas} falhas.")
            return jsonify({
                "message": f"📢 Campanha '{nome_evento}' concluída: {enviados} enviados, {falhas} falhas.",
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
                adicionar_na_fila(f["telefone"], f["mensagem"])
                reprocessados += 1

            return jsonify({
                "message": f"🔄 {reprocessados} mensagens com falha reprocessadas via fila."
            }), 200

        except Exception as e:
            logging.exception(f"Erro ao reprocessar falhas: {e}")
            return jsonify({"error": "Falha ao reprocessar"}), 500


    # ------------------------------------------------
    # 📊 4. Status de Campanhas
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

            logging.info(f"📊 {len(resultado)} campanhas resumidas com sucesso.")
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
