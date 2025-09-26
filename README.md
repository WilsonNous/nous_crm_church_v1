
# Nous CRM Church - Enhanced (by Jullius for Will)

**Resumo rápido:** eu analisei a versão que você enviou, corrigi integrações que estavam quebrando o fluxo (IA e Twilio) substituindo por mocks/shims para permitir execução local sem credenciais externas, saneei o acesso ao banco (fallback SQLite) e reparei arquivos corrompidos/restaurei backups quando necessário. Gereis um pacote pronto para testes locais e para você subir no GitHub privado.

## O que eu alterei (destacado)
- **ia_integracao.py**: substituído por um *mock* seguro que implementa `IAIntegracao.responder_pergunta(...)` — não faz chamadas externas. Isso evita falhas causadas pela integração externa de IA durante desenvolvimento.
- **Twilio**: adicionei um pacote shim local `twilio/` que provê `rest.Client` e `twiml.messaging_response.MessagingResponse` para testes offline. Também restaurei `botmsg.py` a partir do backup original e coloquei variáveis de ambiente dummy para testes locais.
- **database.py**: removi credenciais hard-coded do fluxo de execução, adicionei um wrapper `get_db_connection()` que usa `USE_SQLITE=1` por padrão e faz fallback para MySQL se `USE_SQLITE=0`. Corrigi exceções e normalizei comportamento para SQLite.
- **Vários arquivos**: corrigi problemas de indentação e restaurei backups quando detectei corrupção no arquivo original.

## O que está mockado / substituído (importante)
- **IA**: o módulo `ia_integracao.py` está em modo *mock* (retorna respostas fictícias). Para usar a integração real, substitua por sua implementação e garanta as variáveis de ambiente de API.
- **Twilio**: há um shim local. Para usar Twilio real, configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` e remova/ignore o pacote local `twilio/` (ou instale `twilio` via pip) antes de deploy.

## Como rodar local (passos rápidos)
1. Instale dependências (repositório inclui `requirements.txt`, ajuste conforme necessário):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
> Observação: no ambiente onde eu executei (sandbox), algumas libs não estavam disponíveis; eu usei shims/mocks para permitir execução sem instalar Twilio e sem ter `flask_jwt_extended` — no seu ambiente local de desenvolvimento você pode instalar todas as dependências reais.

2. Crie o banco SQLite (opcional — o `database_setup.py` já cria):
```bash
python database_setup.py
```

3. Variáveis de ambiente úteis (teste):
```bash
export USE_SQLITE=1
export SQLITE_DB_FILE=./crm_visitantes.db
export FLASK_SECRET_KEY="uma_senha_forte"
export JWT_SECRET_KEY="uma_senha_forte"
export TWILIO_ACCOUNT_SID="MOCK_SID"
export TWILIO_AUTH_TOKEN="MOCK_TOKEN"
export TWILIO_PHONE_NUMBER="+15551234567"
python crmlogic.py
# ou com gunicorn:
# gunicorn -w 4 -b 0.0.0.0:5000 crmlogic:app
```
Abra `http://localhost:5000/health` para checar status.

## Deploy
- Para deploy no **Render** defina as variáveis de ambiente acima no painel do serviço. Se for usar o Twilio real, não inclua o shim `twilio/` no repo ou instale a lib `twilio` via pip durante build.
- Para usar MySQL/Cloud SQL: `USE_SQLITE=0` e configure `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB` no ambiente do host.

## O que testei aqui (smoke tests)
- `/health` → 200 OK.
- `/visitantes` → 200 (retorna lista, possivelmente vazia).
- Listei rotas e fiz requisições GET a vários endpoints para checar erros críticos. Algumas rotas administrativas/integrativas foram mockadas ou protegidas por variáveis de ambiente (Twilio/IA) e agora respondem sem falhas de import.

## Arquivos importantes gerados
- `crm_visitantes.db` — banco SQLite criado pelo `database_setup.py`.
- `twilio/` — shim para testes locais.
- `ia_integracao.py` — mock da integração IA.
- `nous_crm_church_v1-main-enhanced.zip` — pacote final pronto para upload.

## Próximos passos recomendados
1. Revisar `ia_integracao.py` e conectar ao provedor real (rotacionar chaves e configurar via env vars).
2. Remover qualquer credencial do repositório e criar `.env.example` (já criei neste pacote um `.env.example`).
3. Preparar um `Dockerfile` e um workflow de GitHub Actions para CI/CD com deploy automático para Render (posso gerar).
4. Revisar e escrever testes automatizados (pytest) para as rotas principais.
