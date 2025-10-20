# ================================================
# routes/campanhas.py
# ================================================
# 📢 Rotas de Campanhas e Eventos - CRM Church
# -----------------------------------------------
# Funções:
# - Filtro de visitantes por data, idade e gênero
# - Envio de campanhas via Z-API
# - Reprocessamento de falhas
# - Consulta de status das campanhas
# ================================================

from flask import Blueprint, request, jsonify
from datetime import datetime, date
from models import db, Visitante, Campanha, EnvioWhatsApp
from utils.jwt_utils import verificar_token
import logging
import requests

bp_campanhas = Blueprint('campanhas', __name__, url_prefix='/api')

# ------------------------------------------------
# 🔧 Configurações Z-API (ajuste conforme ambiente)
# ------------------------------------------------
ZAPI_URL = "https://api.z-api.io/instances/YOUR_INSTANCE/token/YOUR_TOKEN/send-messages"
ZAPI_INSTANCE = "YOUR_INSTANCE"
ZAPI_TOKEN = "YOUR_TOKEN"

logger = logging.getLogger("campanhas")
logger.setLevel(logging.INFO)


# ------------------------------------------------
# 🧩 Função auxiliar: cálculo de idade
# ------------------------------------------------
def calcular_idade(data_nascimento):
    if not data_nascimento:
        return None
    hoje = date.today()
    return hoje.year - data_nascimento.year - (
        (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day)
    )


# ------------------------------------------------
# 🔍 1. Filtro de Visitantes
# ------------------------------------------------
@bp_campanhas.route('/visitantes/filtro', methods=['POST'])
@verificar_token
def filtrar_visitantes(usuario_atual):
    try:
        data = request.get_json()
        data_inicio = datetime.strptime(data['dataInicio'], "%Y-%m-%d").date()
        data_fim = datetime.strptime(data['dataFim'], "%Y-%m-%d").date()
        idade_min = data.get('idadeMin')
        idade_max = data.get('idadeMax')
        genero = data.get('genero')

        query = Visitante.query.filter(
            Visitante.data_cadastro.between(data_inicio, data_fim)
        )

        if genero:
            query = query.filter(Visitante.genero == genero)

        visitantes = query.all()

        resultado = []
        for v in visitantes:
            idade = calcular_idade(v.data_nascimento)
            if idade_min and idade < int(idade_min):
                continue
            if idade_max and idade > int(idade_max):
                continue

            resultado.append({
                "nome": v.nome,
                "genero": v.genero,
                "idade": idade,
                "telefone": v.telefone,
                "data_cadastro": v.data_cadastro.strftime("%d/%m/%Y")
            })

        return jsonify({"visitantes": resultado})

    except Exception as e:
        logger.error(f"Erro no filtro de visitantes: {e}")
        return jsonify({"error": "Falha ao processar filtros"}), 500


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

        # Cria registro de campanha
        campanha = Campanha(
            nome_evento=nome_evento,
            mensagem=mensagem,
            imagem=imagem,
            criado_por=usuario_atual,
            data_envio=datetime.now()
        )
        db.session.add(campanha)
        db.session.commit()

        # Busca visitantes ativos (poderia vir dos filtros também)
        visitantes = Visitante.query.all()
        enviados, falhas = 0, 0

        for v in visitantes:
            try:
                payload = {
                    "phone": v.telefone,
                    "message": f"📢 {mensagem}",
                    "image": imagem
                }

                # Exemplo: envio real (pode ser desativado em dev)
                # requests.post(ZAPI_URL, json=payload, timeout=10)

                enviados += 1
                envio = EnvioWhatsApp(
                    visitante_id=v.id,
                    campanha_id=campanha.id,
                    status="enviado",
                    data_envio=datetime.now()
                )
                db.session.add(envio)
            except Exception as e:
                falhas += 1
                envio = EnvioWhatsApp(
                    visitante_id=v.id,
                    campanha_id=campanha.id,
                    status="falha",
                    data_envio=datetime.now()
                )
                db.session.add(envio)
                logger.error(f"Falha no envio para {v.telefone}: {e}")

        campanha.status = "finalizada"
        campanha.enviados = enviados
        campanha.falhas = falhas
        db.session.commit()

        logger.info(f"Campanha '{nome_evento}' enviada: {enviados} enviados, {falhas} falhas.")
        return jsonify({"message": f"Campanha '{nome_evento}' enviada com sucesso!"})

    except Exception as e:
        logger.error(f"Erro ao enviar campanha: {e}")
        return jsonify({"error": "Falha ao enviar campanha"}), 500


# ------------------------------------------------
# 🔁 3. Reprocessar Falhas
# ------------------------------------------------
@bp_campanhas.route('/campanhas/reprocessar', methods=['POST'])
@verificar_token
def reprocessar_falhas(usuario_atual):
    try:
        ultima_campanha = Campanha.query.order_by(Campanha.id.desc()).first()
        if not ultima_campanha:
            return jsonify({"message": "Nenhuma campanha encontrada."})

        falhas = EnvioWhatsApp.query.filter_by(
            campanha_id=ultima_campanha.id,
            status="falha"
        ).all()

        reprocessados = 0
        for envio in falhas:
            visitante = Visitante.query.get(envio.visitante_id)
            if not visitante:
                continue
            try:
                payload = {
                    "phone": visitante.telefone,
                    "message": ultima_campanha.mensagem,
                    "image": ultima_campanha.imagem
                }
                # requests.post(ZAPI_URL, json=payload, timeout=10)
                envio.status = "reprocessado"
                reprocessados += 1
            except Exception as e:
                logger.error(f"Erro ao reprocessar {visitante.telefone}: {e}")

        db.session.commit()
        return jsonify({"message": f"🔄 {reprocessados} falhas reprocessadas com sucesso."})

    except Exception as e:
        logger.error(f"Erro ao reprocessar falhas: {e}")
        return jsonify({"error": "Falha ao reprocessar"}), 500


# ------------------------------------------------
# 📊 4. Status de Campanhas
# ------------------------------------------------
@bp_campanhas.route('/campanhas/status', methods=['GET'])
@verificar_token
def status_campanhas(usuario_atual):
    try:
        campanhas = Campanha.query.order_by(Campanha.data_envio.desc()).limit(10).all()
        resultado = []
        for c in campanhas:
            resultado.append({
                "data_envio": c.data_envio.strftime("%d/%m/%Y %H:%M"),
                "nome_evento": c.nome_evento,
                "enviados": c.enviados or 0,
                "falhas": c.falhas or 0,
                "status": c.status
            })
        return jsonify({"status": resultado})

    except Exception as e:
        logger.error(f"Erro ao obter status: {e}")
        return jsonify({"error": "Falha ao carregar status"}), 500
