# Deploy na Railway

App testada em modo produção (gunicorn + 2 uvicorn workers, healthcheck em `/health`).

## 1. Subir pro GitHub

```bash
cd uniassinatura-api
git init
git add .
git commit -m "UNIASSINATURA API: custodia de PFX + assinatura PAdES por CPF"
git branch -M main
git remote add origin https://github.com/jacksontomelin/UNIASSINATURA.git
git push -u origin main
```

O `.gitignore` já bloqueia `.env`, `*.pfx`, `*.db`. A MASTER_KEY nunca vai pro repo.

## 2. Criar o projeto na Railway

- New Project -> Deploy from GitHub repo -> escolhe `UNIASSINATURA`.
- A Railway detecta o `Dockerfile` e o `railway.json` sozinha (build via Dockerfile, healthcheck `/health`).

## 3. Adicionar o Postgres

- No projeto: New -> Database -> PostgreSQL.
- A Railway cria a var `DATABASE_URL`. **Atencao ao formato**: por padrao vem `postgresql://...`, mas o SQLAlchemy com psycopg 3 precisa de `postgresql+psycopg://...`.
- Opcao A: no serviço da API, crie a var `DATABASE_URL` referenciando o Postgres e troque o prefixo pra `postgresql+psycopg://`.
- Opcao B (mais simples): use a Reference Variable do Postgres e ajuste o esquema. Ex.:
  `DATABASE_URL = ${{Postgres.DATABASE_URL}}` e depois edite pra começar com `postgresql+psycopg://`.

## 4. Variáveis de ambiente (aba Variables da API)

```
MASTER_KEY=<gere e cole>        # NUNCA reutilize / NUNCA perca (destranca os PFX)
BOOTSTRAP_TOKEN=<segredo forte>
DATABASE_URL=postgresql+psycopg://...   # do passo 3
TSA_URL=                        # opcional, TSA ICP-Brasil
```

Gerar a MASTER_KEY (rode local):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> IMPORTANTE: a MASTER_KEY criptografa os PFX no banco. Se ela mudar ou se perder, os certificados já salvos ficam ilegíveis. Guarde num cofre (o próprio secret manager da Railway serve, mas tenha um backup).

## 5. Deploy e primeiro acesso

- A Railway builda e sobe. Gera um domínio público (Settings -> Networking -> Generate Domain).
- Testa: `curl https://SEU-DOMINIO.up.railway.app/health`
- Cria o admin:
  ```bash
  curl -X POST https://SEU-DOMINIO.up.railway.app/admin/bootstrap \
    -H "X-Bootstrap-Token: SEU_BOOTSTRAP_TOKEN"
  ```
  Guarde o `api_key` e `api_secret` retornados (o secret só aparece aqui).

Pronto. A partir daí é o fluxo do README: registrar PFX por CPF, criar clientes externos, conceder autorizações, assinar.

## Notas de produção

- **HTTPS**: a Railway já entrega TLS no domínio. Nunca exponha isso em HTTP puro (os secrets viajam no header).
- **Escala**: 2 workers dão conta de bastante coisa. Assinatura é CPU-bound (cripto); se precisar, suba workers ou o plano.
- **Backup**: o Postgres guarda os PFX cifrados. Backup do banco = backup dos certificados (mas inúteis sem a MASTER_KEY).
- **Migrations**: a app cria as tabelas no boot (idempotente). Se for evoluir o schema, considere Alembic depois.
