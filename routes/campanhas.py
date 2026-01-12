# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Envio 100% texto (sem imagem) para máxima entregabilidade
# ✅ Enfileira e só marca "enviado" após confirmação real do worker
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
                    "id": v.get("id"),
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
    # ✅ Helpers (factories) para callbacks de fila
    # ------------------------------------------------
    def _on_success_factory(visitante_id: int, evento_nome: str, telefone: str, mensagem: str):
        def _cb(_res=None):
            # 1) salva conversa
            try:
                salvar_conversa(
                    numero=telefone,
                    mensagem=mensagem,
                    tipo="enviada",
                    sid=None,
                    origem="campanha"
                )
            except Exception as e:
                logging.error(f"❌ salvar_conversa (campanha) tel={telefone}: {e}")

            # 2) marca como enviado no banco
            try:
                database.atualizar_status_envio_evento(visitante_id, evento_nome, "enviado")
            except Exception as e:
                logging.error(
                    f"❌ atualizar_status_envio_evento(enviado) vid={visitante_id} ev={evento_nome}: {e}"
                )
        return _cb


    def _on_fail_factory(visitante_id: int, evento_nome: str):
        def _cb(_res=None):
            try:
                database.atualizar_status_envio_evento(visitante_id, evento_nome, "falha")
            except Exception as e:
                logging.error(
                    f"❌ atualizar_status_envio_evento(falha) vid={visitante_id} ev={evento_nome}: {e}"
                )
        return _cb


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
            erro_registro = 0

            for v in visitantes:
                visitante_id = v.get("id")
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
                    erro_registro += 1
                    logging.error(f"❌ Falha ao registrar envio_evento (pendente) p/ {nome}: {e}")
                    continue

                # 2) Sem telefone => falha imediata
                if not telefone:
                    sem_telefone += 1
                    try:
                        database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    except Exception as e:
                        logging.error(f"❌ atualizar_status_envio_evento(falha) sem telefone vid={visitante_id}: {e}")
                    logging.warning(f"⚠️ Visitante sem telefone: {nome}")
                    continue

                # 3) Marca como em fila
                try:
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "em_fila")
                except Exception as e:
                    logging.error(f"❌ atualizar_status_envio_evento(em_fila) vid={visitante_id}: {e}")

                # 4) Callbacks para confirmar somente após envio real
                on_success = _on_success_factory(visitante_id, nome_evento, telefone, mensagem)
                on_fail = _on_fail_factory(visitante_id, nome_evento)

                # 5) Enfileira (não salva conversa e não marca enviado aqui!)
                ok_fila = adicionar_na_fila(
                    telefone,
                    mensagem,
                    imagem_url=None,
                    on_success=on_success,
                    on_fail=on_fail,
                    meta={
                        "origem": "campanha",
                        "evento": nome_evento,
                        "visitante_id": visitante_id
                    }
                )

                if ok_fila:
                    enfileirados += 1
                    logging.info(f"📬 Visitante {nome} enfileirado para campanha '{nome_evento}'.")
                else:
                    # se nem enfileirou, já marca falha
                    on_fail()
                    logging.error(f"❌ Falha ao enfileirar tel={telefone} (campanha).")

            return jsonify({
                "message": f"📢 Campanha '{nome_evento}' enfileirada.",
                "total_alvo": len(visitantes),
                "enfileirados": enfileirados,
                "sem_telefone": sem_telefone,
                "erro_registro": erro_registro,
                "obs": "O status 'enviado' será marcado automaticamente após o envio real na fila."
            }), 200

        except Exception as e:
            logging.exception(f"Erro geral ao enviar campanha: {e}")
            return jsonify({"error": "Erro ao enviar campanha"}), 500


    # ------------------------------------------------
    # 🔁 3. Reprocessar Falhas (reenfileira e confirma depois)
    # ------------------------------------------------
    @app.route('/api/campanhas/reprocessar', methods=['POST'])
    def reprocessar_falhas():
        try:
            envios = database.listar_envios_eventos(limit=200) or []
            falhas = [e for e in envios if (e.get("status") == "falha")]
            reprocessados = 0
            ignorados = 0

            for f in falhas:
                telefone = f.get("telefone")
                mensagem = f.get("mensagem")
                evento_nome = f.get("evento_nome")
                visitante_id = f.get("visitante_id")

                if not telefone or not mensagem or not evento_nome or not visitante_id:
                    ignorados += 1
                    continue

                # Marca como em fila
                try:
                    database.atualizar_status_envio_evento(visitante_id, evento_nome, "em_fila")
                except Exception as e:
                    logging.error(f"❌ atualizar_status_envio_evento(em_fila) reprocesso vid={visitante_id}: {e}")

                on_success = _on_success_factory(visitante_id, evento_nome, telefone, mensagem)
                on_fail = _on_fail_factory(visitante_id, evento_nome)

                adicionar_na_fila(
                    telefone,
                    mensagem,
                    imagem_url=None,
                    on_success=on_success,
                    on_fail=on_fail,
                    meta={
                        "origem": "campanha_reprocesso",
                        "evento": evento_nome,
                        "visitante_id": visitante_id
                    }
                )
                reprocessados += 1

            return jsonify({
                "message": f"🔄 {reprocessados} falhas reenfileiradas.",
                "ignorados": ignorados
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
                    "nome_evento": c.get("evento_nome"),
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
