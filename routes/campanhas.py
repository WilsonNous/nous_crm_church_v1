# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# Integra-se com o database.py (PyMySQL)
# ================================================

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from utils.jwt_utils import verificar_token
import database  # usa as funções do seu database.py

bp_campanhas = Blueprint('campanhas', __name__, url_prefix='/api')
logger = logging.getLogger("campanhas")


# ------------------------------------------------
# 🔍 1. Filtro de Visitantes
# ------------------------------------------------
@bp_campanhas.route('/visitantes/filtro', methods=['POST'])
@verificar_token
def filtrar_visitantes(usuario_atual):
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
            # calcula idade se houver data de nascimento
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
        logger.exception(f"❌ Erro ao filtrar visitantes: {e}")
        return jsonify({"error": "Erro ao filtrar visitantes"}), 500


# ------------------------------------------------
# 📢 2. Enviar Campanha
# ------------------------------------------------
@bp_campanhas.route('/campanhas/enviar', methods=['POST'])
@verificar_token
def enviar_campanha(usuario_atual):
    try:
        data = request.get_json()
        nome_evento = data.get("nome_evento")
        mensagem = data.get("mensagem")
        imagem = data.get("imagem")

        visitantes = database.filtrar_visitantes_para_evento()  # pega todos ou filtrados
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

        logger.info(f"📢 Campanha '{nome_evento}' registrada: {enviados} enviados, {falhas} falhas.")
        return jsonify({"message": f"Campanha '{nome_evento}' enviada com sucesso!", "enviados": enviados, "falhas": falhas}), 200

    except Exception as e:
        logger.exception(f"Erro ao enviar campanha: {e}")
        return jsonify({"error": "Erro ao enviar campanha"}), 500


# ------------------------------------------------
# 🔁 3. Reprocessar Falhas
# ------------------------------------------------
@bp_campanhas.route('/campanhas/reprocessar', methods=['POST'])
@verificar_token
def reprocessar_falhas(usuario_atual):
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

        return jsonify({"message": f"🔄 {reprocessados} falhas reprocessadas com sucesso."}), 200

    except Exception as e:
        logger.exception(f"Erro ao reprocessar falhas: {e}")
        return jsonify({"error": "Falha ao reprocessar"}), 500


# ------------------------------------------------
# 📊 4. Status de Campanhas
# ------------------------------------------------
@bp_campanhas.route('/campanhas/status', methods=['GET'])
@verificar_token
def status_campanhas(usuario_atual):
    try:
        envios = database.listar_envios_eventos(limit=100)
        if not envios:
            return jsonify({"status": []}), 200

        resultado = []
        for e in envios:
            resultado.append({
                "data_envio": e["data_envio"].strftime("%d/%m/%Y %H:%M") if e["data_envio"] else "-",
                "nome_evento": e["evento_nome"],
                "enviados": "-",  # pode ser adicionado se quiser agregar
                "falhas": "-",
                "status": e["status"]
            })

        return jsonify({"status": resultado}), 200

    except Exception as e:
        logger.exception(f"Erro ao obter status de campanhas: {e}")
        return jsonify({"error": "Falha ao carregar status"}), 500
