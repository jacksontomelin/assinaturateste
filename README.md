# UNIASSINATURA API

API de custódia de certificados A1 (PFX) e assinatura digital PAdES, com controle de acesso **por CPF + autorização**. Sistemas externos consomem via API key/secret e só assinam pelos CPFs que foram explicitamente autorizados. Toda assinatura fica registrada (quem, quando, qual documento, IP).

## Como funciona o controle

- **CPF** = identifica de quem é o certificado (o titular do A1).
- **Cliente externo** = cada sistema que consome a API tem `api_key` + `api_secret`.
- **Autorização (grant)** = liga um cliente a um CPF, definindo se pode `assinar` e/ou `consultar`, com validade opcional.
- **Auditoria** = cada `/v1/sign` grava um registro (hash do doc, IP, user-agent, resultado, timestamp).

O admin custodia os PFX e distribui as autorizações. Cliente externo nunca vê o PFX.

## Rodando local

```bash
pip install -r requirements.txt
cp .env.example .env
# gere a MASTER_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# cole no .env, ajuste o BOOTSTRAP_TOKEN
uvicorn app.main:app --reload
```

Docs interativas: http://localhost:8000/docs

## Deploy Railway

- Adicione o Postgres, aponte `DATABASE_URL` (formato `postgresql+psycopg://...`).
- Set `MASTER_KEY` e `BOOTSTRAP_TOKEN` nas variáveis. **Nunca** commite a MASTER_KEY.
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Fluxo de uso

### 1. Criar o admin (uma vez)
```bash
curl -X POST $URL/admin/bootstrap -H "X-Bootstrap-Token: SEU_TOKEN"
# devolve api_key + api_secret do admin (guarde, o secret só aparece aqui)
```

### 2. Registrar um PFX pra um CPF (admin)
```bash
curl -X POST $URL/certificates \
  -H "X-API-Key: ADMIN_KEY" -H "X-API-Secret: ADMIN_SECRET" \
  -F "cpf=12345678909" -F "password=SENHA_DO_PFX" -F "pfx=@cert.pfx"
```

### 3. Criar um cliente externo (admin)
```bash
curl -X POST $URL/admin/clients \
  -H "X-API-Key: ADMIN_KEY" -H "X-API-Secret: ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"name":"Sistema Parceiro X"}'
# devolve api_key + api_secret do parceiro
```

### 4. Autorizar o cliente a usar um CPF (admin)
```bash
curl -X POST $URL/admin/authorizations \
  -H "X-API-Key: ADMIN_KEY" -H "X-API-Secret: ADMIN_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"client_id":"ID_DO_CLIENTE","cpf":"12345678909","can_sign":true,"can_read":true}'
```

### 5. Cliente externo assina (via CPF)
```bash
curl -X POST $URL/v1/sign \
  -H "X-API-Key: PARCEIRO_KEY" -H "X-API-Secret: PARCEIRO_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"cpf":"12345678909","pdf_base64":"JVBERi0...","document_name":"procuracao.pdf"}'
# devolve o signed_pdf_base64 + signature_id
```

### 6. Consultar quantas vezes assinou
```bash
curl "$URL/v1/signatures/count?cpf=12345678909" \
  -H "X-API-Key: PARCEIRO_KEY" -H "X-API-Secret: PARCEIRO_SECRET"
# {"cpf":"...","total":3,"ok":3,"error":0,"last_signed_at":"..."}

curl "$URL/v1/signatures?cpf=12345678909" \
  -H "X-API-Key: PARCEIRO_KEY" -H "X-API-Secret: PARCEIRO_SECRET"
# histórico completo
```

## Endpoints

| Método | Rota | Acesso | O que faz |
|---|---|---|---|
| POST | `/admin/bootstrap` | token | Cria o primeiro admin |
| POST | `/admin/clients` | admin | Cria cliente externo |
| GET | `/admin/clients` | admin | Lista clientes |
| POST | `/admin/clients/{id}/deactivate` | admin | Desativa cliente |
| POST | `/admin/authorizations` | admin | Concede grant (CPF + permissões) |
| GET | `/admin/authorizations` | admin | Lista grants |
| POST | `/admin/authorizations/{id}/revoke` | admin | Revoga grant |
| POST | `/certificates` | admin | Registra PFX pra um CPF |
| GET | `/certificates` | admin | Lista certificados |
| GET | `/certificates/{cpf}` | admin | Status/validade do cert do CPF |
| POST | `/v1/sign` | cliente + grant sign | Assina PDF pelo CPF |
| GET | `/v1/signatures?cpf=` | cliente + grant read | Histórico de assinaturas |
| GET | `/v1/signatures/count?cpf=` | cliente + grant read | Contagem (quantas vezes assinou) |

## Segurança

- PFX e senha do PFX ficam **criptografados em repouso** (Fernet, chave em `MASTER_KEY` fora do banco).
- Secrets dos clientes são hasheados (bcrypt), nunca guardados em texto.
- Autenticação por header `X-API-Key` + `X-API-Secret`; autorização por grant explícito por CPF.
- **LGPD**: guardar PFX de terceiro exige termo de custódia autorizando. Registre a base legal.

## Carimbo de tempo (PAdES-T)

Sem `TSA_URL` a assinatura usa o horário do servidor (PAdES-B, prova mais fraca). Com uma TSA ICP-Brasil configurada em `TSA_URL`, vira PAdES-T com carimbo confiável. Rode atrás de HTTPS sempre.
