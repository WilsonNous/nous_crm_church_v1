# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Envio 100% texto (sem imagem) para máxima entregabilidade
# ✅ Enfileira e só marca "enviado" após confirmação real do worker (DB Queue)
# ================================================

import logging
from flask import request, jsonify
from datetime import datetime
from contextlib import closing

import database
from database import get_db_connection
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
            ) or []

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
    # Helpers (opcionais) - anti duplicidade
    # ------------------------------------------------
    def _envio_ja_existe(visitante_id: int, evento_nome: str) -> bool:
        """
        Evita duplicar campanhas se o mesmo evento for disparado duas vezes.
        Considera como "já existe" qualquer status diferente de 'falha'.
        """
        try:
            with closing(get_db_connection()) as conn:
                if not conn:
                    return False  # se sem conexão, não bloqueia
                cur = conn.cursor()
                cur.execute("""
                    SELECT 1
                    FROM eventos_envios
                    WHERE visitante_id = %s
                      AND evento_nome = %s
                      AND status <> 'falha'
                    LIMIT 1
                """, (int(visitante_id), str(evento_nome)))
                return cur.fetchone() is not None
        except Exception:
            return False


    # ------------------------------------------------
    # 📢 2. Enviar Campanha (enfileira e CONFIRMA no worker)
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
            ) or []

            if not visitantes:
                return jsonify({"message": "Nenhum visitante encontrado para envio."}), 200

            enfileirados = 0
            sem_telefone = 0
            erro_registro = 0
            erro_fila = 0
            pulados_duplicidade = 0

            # ⚠️ Anti-timeout: nada de chamar Z-API aqui. Só DB.
            for v in visitantes:
                visitante_id = v.get("id")
                telefone = v.get("telefone")
                nome = v.get("nome") or "-"

                if not visitante_id:
                    erro_registro += 1
                    logging.error(f"❌ Visitante sem ID válido (nome={nome}). Ignorando.")
                    continue

                # (Opcional) evita duplicar se já existe envio desse evento (exceto falha)
                if _envio_ja_existe(visitante_id, nome_evento):
                    pulados_duplicidade += 1
                    continue

                # 1) Registra envio (pendente) — fica em eventos_envios
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

                # 3) Marca como em fila (quem marca ENVIADO é o worker)
                try:
                    database.atualizar_status_envio_evento(visitante_id, nome_evento, "em_fila")
                except Exception as e:
                    logging.error(f"❌ atualizar_status_envio_evento(em_fila) vid={visitante_id}: {e}")

                # 4) Enfileira no MySQL (fila_envios)
                ok_fila = adicionar_na_fila(
                    telefone,
                    mensagem,
                    imagem_url=None,
                    meta={
                        "origem": "campanha",
                        "evento": nome_evento,
                        "visitante_id": int(visitante_id),
                        "telefone_raw": telefone
                    }
                )

                if ok_fila:
                    enfileirados += 1
                    logging.info(f"📬 Visitante {nome} enfileirado para campanha '{nome_evento}'.")
                else:
                    erro_fila += 1
                    try:
                        database.atualizar_status_envio_evento(visitante_id, nome_evento, "falha")
                    except Exception:
                        pass
                    logging.error(f"❌ Falha ao enfileirar tel={telefone} (campanha).")

            return jsonify({
                "message": f"📢 Campanha '{nome_evento}' enfileirada.",
                "total_alvo": len(visitantes),
                "enfileirados": enfileirados,
                "sem_telefone": sem_telefone,
                "erro_registro": erro_registro,
                "erro_fila": erro_fila,
                "pulados_duplicidade": pulados_duplicidade,
                "obs": "O status 'enviado' será marcado automaticamente após o envio real pelo worker (DB Queue)."
            }), 200

        except Exception as e:
            logging.exception(f"Erro geral ao enviar campanha: {e}")
            return jsonify({"error": "Erro ao enviar campanha"}), 500


    # ------------------------------------------------
    # 🔁 3. Reprocessar Falhas (reenfileira)
    # ------------------------------------------------
    @app.route('/api/campanhas/reprocessar', methods=['POST'])
    def reprocessar_falhas():
        try:
            # ✅ Busca direto no DB as falhas (com visitante_id garantido)
            with closing(get_db_connection()) as conn:
                if not conn:
                    return jsonify({"error": "Sem conexão com o banco"}), 500

                cur = conn.cursor()
                cur.execute("""
                    SELECT
                        e.id AS envio_id,
                        e.visitante_id,
                        e.evento_nome,
                        e.mensagem,
                        v.telefone
                    FROM eventos_envios e
                    JOIN visitantes v ON v.id = e.visitante_id
                    WHERE e.status = 'falha'
                    ORDER BY e.data_envio DESC
                    LIMIT 400
                """)
                falhas = cur.fetchall() or []

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

                ok_fila = adicionar_na_fila(
                    telefone,
                    mensagem,
                    imagem_url=None,
                    meta={
                        "origem": "campanha_reprocesso",
                        "evento": evento_nome,
                        "visitante_id": int(visitante_id),
                        "telefone_raw": telefone
                    }
                )

                if ok_fila:
                    reprocessados += 1
                else:
                    ignorados += 1

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
            campanhas = database.obter_resumo_campanhas(limit=100) or []

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
