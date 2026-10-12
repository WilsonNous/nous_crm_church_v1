"""Cadastro público: somente inserção de visitantes, sem sessão administrativa."""
import logging
from datetime import date
import re
import time
from collections import defaultdict, deque
from threading import Lock
from flask import Blueprint, jsonify, render_template, request
from database import salvar_visitante, visitante_existe, normalizar_para_recebimento

cadastro_publico_bp = Blueprint("cadastro_publico", __name__)
_tentativas = defaultdict(deque)
_trava = Lock()
_LIMITE = 8
_JANELA = 3600

@cadastro_publico_bp.get("/cadastro-visitante")
def pagina_cadastro_publico():
    return render_template("cadastro_visitante_publico.html")

@cadastro_publico_bp.post("/api/public/visitantes")
def cadastrar_visitante_publico():
    if request.content_length and request.content_length > 12000:
        return jsonify(error="Dados excedem o tamanho permitido."), 413
    if not request.is_json:
        return jsonify(error="Envie os dados em JSON."), 415
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(error="Dados inválidos."), 400
    if dados.get("website"):  # campo invisível para robôs
        return jsonify(message="Cadastro recebido."), 200

    ip = request.remote_addr or "desconhecido"
    agora = time.monotonic()
    with _trava:
        fila = _tentativas[ip]
        while fila and agora - fila[0] > _JANELA:
            fila.popleft()
        if len(fila) >= _LIMITE:
            return jsonify(error="Muitas tentativas. Tente novamente mais tarde."), 429
        fila.append(agora)

    nome = str(dados.get("name") or "").strip()
    telefone_bruto = re.sub(r"\D", "", str(dados.get("phone") or ""))
    if not 3 <= len(nome) <= 120 or not re.fullmatch(r"\d{11}", telefone_bruto):
        return jsonify(error="Informe nome completo e telefone com DDD (11 dígitos)."), 400
    email = str(dados.get("email") or "").strip()
    if len(email) > 150 or (email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
        return jsonify(error="E-mail inválido."), 400
    campos = ("city", "gender", "maritalStatus", "currentChurch", "referral", "contactTime")
    if any(len(str(dados.get(c) or "")) > 150 for c in campos):
        return jsonify(error="Um dos campos excede o limite permitido."), 400
    cidade = str(dados.get("city") or "").strip()
    genero = str(dados.get("gender") or "").strip()
    estado_civil = str(dados.get("maritalStatus") or "").strip()
    if not cidade or len(cidade) > 150:
        return jsonify(error="Informe sua cidade."), 400
    if genero not in {"masculino", "feminino", "outro", "nao_informado"}:
        return jsonify(error="Selecione uma opção para gênero."), 400
    if estado_civil not in {"solteiro", "casado", "divorciado", "viuvo", "outro", "nao_informado"}:
        return jsonify(error="Selecione uma opção para estado civil."), 400
    oracao = str(dados.get("prayerRequest") or "").strip()
    if len(oracao) > 2000:
        return jsonify(error="Pedido de oração muito longo."), 400
    nascimento = str(dados.get("birthdate") or "").strip()
    try:
        nascimento_data = date.fromisoformat(nascimento)
        if nascimento_data > date.today() or nascimento_data.year < 1900:
            raise ValueError("Data fora do intervalo")
    except ValueError:
        return jsonify(error="Informe uma data de nascimento válida."), 400
    try:
        telefone = normalizar_para_recebimento(telefone_bruto)
        if visitante_existe(telefone):
            return jsonify(error="Este telefone já está cadastrado. Procure a equipe de acolhimento."), 409
        ok = salvar_visitante(
            nome=nome, telefone=telefone, email=email or None,
            data_nascimento=nascimento or None, cidade=cidade,
            genero=genero, estado_civil=estado_civil,
            igreja_atual=dados.get("currentChurch") or None,
            frequenta_igreja=1 if dados.get("attendingChurch") is True else 0,
            indicacao=dados.get("referral") or None,
            membro=bool(dados.get("membership")),
            pedido_oracao=oracao or None, horario_contato=dados.get("contactTime") or None
        )
        if ok:
            return jsonify(message="Cadastro realizado com sucesso! Seja bem-vindo(a)."), 201
        return jsonify(error="Não foi possível concluir o cadastro."), 500
    except Exception:
        logging.exception("Falha no cadastro público de visitante")
        return jsonify(error="Não foi possível concluir o cadastro. Tente novamente."), 500
