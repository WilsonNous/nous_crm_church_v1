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
            filtros = request.get_json() or {}
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
                nasc = v.get("data_nascimento")
                if nasc and isinstance(nasc, datetime):
                    idade = datetime.now().year - nasc.year - (
                        (datetime.now().month, datetime.now().day) < (nasc.month, nasc.day)
                    )

                resultado.append({
                    "id": v["id"],
                    "nome": v.get("nome"),
                    "telefone": v.get("telefone"),
                    "genero": v.get("genero"),
                    "idade": idade,
                    "data_cadastro": v["data_cadastro"].strftime("%d/%m/%Y") if v.get("data_cadastro") else "-"
                })

            return jsonify({"visitantes": resultado}), 200

        except Exception as e:
            logging.exception(f"❌ Erro ao filtrar visitantes: {e}")
            return jsonify({"error": "Erro ao filtrar visitantes"}), 500


    # ------------------------------------------------
    # 📢 2. Enviar Campanha (enfileira e CONFIRMA depois)
    # ------------------------------------------------
    @app.route('/api/campanhas/enviar', methods=['POST'])
    def enviar_campanha():
        try:
            data = request.get_json() or {}
            nome_evento = (data.get("nome_evento") or "").strip()
            mensagem = (data.get("mensagem") or "").strip()

            if not nome_evento or not mensagem:
                return jsonify({"error": "nome_evento e mensagem são obrigatórios"}), 400

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

            enfileirados = 0
            sem_telefone = 0

            for v in visitantes:
                visitante_id = v["id"]
                telefone = v.get("telefone")
                nome = v.get("nome") or "-"

                # 1) Registra envio (pendente)
                try:
                    database.salvar_envio_evento(
                        visitante_id=visitante_id,
                        evento_nome=nome_evento,
                        mensagem=mensagem,
                        imagem_url=None,
                        status="pendente",
                        origem="campanha"
                    )
                except Exception as e:
                    logging.error(f"❌ Falha ao registrar envio_evento (pendente) p/ {nome}: {e}")
                    continue

                # 2) Sem telefone => falha imediata
                if not telefone:
                    sem_telefone += 1
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    logging.warning(f"⚠️ Visitante sem telefone: {nome}")
                    continue

                # 3) Marca como em fila (opcional mas recomendado)
                database.atualizar_status_envio_evento(visitante_id, nome_evento, "em_fila")

                # 4) Callbacks para confirmar somente após envio real
                def _on_success(_res=None, vid=visitante_id, ev=nome_evento, tel=telefone, msg=mensagem):
                    try:
                        salvar_conversa(
                            numero=tel,
                            mensagem=msg,
                            tipo="enviada",
                            sid=None,
                            origem="campanha"
                        )
                    except Exception as e:
                        logging.error(f"❌ Erro ao salvar_conversa (campanha) tel={tel}: {e}")

                    try:
                        database.atualizar_status_envio_evento(vid, ev, "enviado")
                    except Exception as e:
                        logging.error(f"❌ Erro ao atualizar_status_envio_evento(enviado) vid={vid}: {e}")

                def _on_fail(_res=None, vid=visitante_id, ev=nome_evento):
                    try:
                        database.atualizar_status_envio_evento(vid, ev, "falha")
                    except Exception as e:
                        logging.error(f"❌ Erro ao atualizar_status_envio_evento(falha) vid={vid}: {e}")

                # 5) Enfileira (não salva conversa e não marca enviado aqui!)
                ok_fila = adicionar_na_fila(
                    telefone,
                    mensagem,
                    imagem_url=None,
                    on_success=_on_success,
                    on_fail=_on_fail
                )

                if ok_fila:
                    enfileirados += 1
                    logging.info(f"📬 Visitante {nome} enfileirado para campanha '{nome_evento}'.")
                else:
                    _on_fail()
                    logging.error(f"❌ Falha ao enfileirar tel={telefone} (campanha).")

            return jsonify({
                "message": f"📢 Campanha '{nome_evento}' enfileirada.",
                "total_alvo": len(visitantes),
                "enfileirados": enfileirados,
                "sem_telefone": sem_telefone,
                "obs": "O status 'enviado' será marcado automaticamente após o envio real na fila."
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
                telefone = f.get("telefone")
                mensagem = f.get("mensagem")
                evento_nome = f.get("evento_nome")
                visitante_id = f.get("visitante_id") or None

                if not telefone or not mensagem:
                    continue

                # Marca como em fila
                if visitante_id and evento_nome:
                    database.atualizar_status_envio_evento(visitante_id, evento_nome, "em_fila")

                def _on_success(_res=None, tel=telefone, msg=mensagem, vid=visitante_id, ev=evento_nome):
                    try:
                        salvar_conversa(numero=tel, mensagem=msg, tipo="enviada", sid=None, origem="campanha")
                    except Exception:
                        pass
                    if vid and ev:
                        database.atualizar_status_envio_evento(vid, ev, "reprocessado")

                def _on_fail(_res=None, vid=visitante_id, ev=evento_nome):
                    if vid and ev:
                        database.atualizar_status_envio_evento(vid, ev, "falha")

                adicionar_na_fila(telefone, mensagem, None, on_success=_on_success, on_fail=_on_fail)
                reprocessados += 1

            return jsonify({"message": f"🔄 {reprocessados} falhas reenfileiradas."}), 200

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
                        "✅ Concluída" if c.get("falhas", 0) == 0 and c.get("pendentes", 0) == 0
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
            return jsonify({"message": f"🧹 Histórico limpo ({total} registros removidos)."}), 200
        except Exception as e:
            logging.exception(f"Erro ao limpar histórico: {e}")
            return jsonify({"error": "Falha ao limpar histórico"}), 500
