#!/usr/bin/env bash
set -e
cd /home/claude/uniassinatura-api

export MASTER_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export BOOTSTRAP_TOKEN="sandbox-token"
export DATABASE_URL="sqlite:///./sandbox.db"
rm -f sandbox.db

# garante assets de teste
python3 - << 'PY'
import os, datetime, io
if not (os.path.exists("sb.pfx") and os.path.exists("sb.pdf")):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME,"BR"),
                   x509.NameAttribute(NameOID.COMMON_NAME,"JACKSON TOMELIN:12345678909")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(n).issuer_name(n)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now+datetime.timedelta(days=365))
            .sign(key, hashes.SHA256()))
    open("sb.pfx","wb").write(pkcs12.serialize_key_and_certificates(
        b"demo", key, cert, None, serialization.BestAvailableEncryption(b"senha123")))
    from reportlab.pdfgen import canvas
    b=io.BytesIO(); c=canvas.Canvas(b); c.drawString(100,750,"Procuracao sandbox"); c.save()
    open("sb.pdf","wb").write(b.getvalue())
print("assets ok")
PY

# sobe servidor UMA vez
uvicorn app.main:app --port 8080 > sb.log 2>&1 &
SRV=$!
trap "kill $SRV 2>/dev/null" EXIT
for i in $(seq 1 20); do
  curl -s http://localhost:8080/health > /dev/null 2>&1 && break
  sleep 0.5
done
B="http://localhost:8080"

jq_get() { python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }

echo "### GET /health"; curl -s $B/health; echo; echo

ADMIN=$(curl -s -X POST $B/admin/bootstrap -H "X-Bootstrap-Token: sandbox-token")
AK=$(echo "$ADMIN"|jq_get api_key); AS=$(echo "$ADMIN"|jq_get api_secret)
echo "### admin criado: $AK"; echo

curl -s -X POST $B/certificates -H "X-API-Key: $AK" -H "X-API-Secret: $AS" \
  -F "cpf=12345678909" -F "password=senha123" -F "pfx=@sb.pfx" > /dev/null
echo "### PFX registrado pro CPF 12345678909"; echo

EXT=$(curl -s -X POST $B/admin/clients -H "X-API-Key: $AK" -H "X-API-Secret: $AS" \
  -H "Content-Type: application/json" -d '{"name":"Sistema Parceiro X"}')
EK=$(echo "$EXT"|jq_get api_key); ES=$(echo "$EXT"|jq_get api_secret); EID=$(echo "$EXT"|jq_get id)
echo "### cliente externo criado: $EK"; echo

PDF_B64=$(base64 -w0 sb.pdf)

echo "### 1) assinar SEM autorizacao (esperado 403)"
curl -s -o /tmp/r.json -w "HTTP %{http_code} -> " -X POST $B/v1/sign \
  -H "X-API-Key: $EK" -H "X-API-Secret: $ES" -H "Content-Type: application/json" \
  -d "{\"cpf\":\"12345678909\",\"pdf_base64\":\"$PDF_B64\"}"
cat /tmp/r.json; echo; echo

echo "### 2) admin autoriza o CPF"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST $B/admin/authorizations \
  -H "X-API-Key: $AK" -H "X-API-Secret: $AS" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$EID\",\"cpf\":\"12345678909\",\"can_sign\":true,\"can_read\":true}"; echo

echo "### 3) assinar COM autorizacao"
curl -s -o /tmp/sign.json -w "HTTP %{http_code}\n" -X POST $B/v1/sign \
  -H "X-API-Key: $EK" -H "X-API-Secret: $ES" -H "Content-Type: application/json" \
  -d "{\"cpf\":\"12345678909\",\"pdf_base64\":\"$PDF_B64\",\"document_name\":\"procuracao.pdf\"}"
python3 -c "import json;d=json.load(open('/tmp/sign.json'));print('  signature_id:',d['signature_id']);print('  hash doc    :',d['document_hash']);print('  tsa_used    :',d['tsa_used']);print('  pdf assinado:',len(d['signed_pdf_base64']),'chars b64')"
python3 -c "import json,base64;open('sb_signed.pdf','wb').write(base64.b64decode(json.load(open('/tmp/sign.json'))['signed_pdf_base64']))"
echo

echo "### 4) mais 2 assinaturas + contagem"
for i in 1 2; do
  curl -s -o /dev/null -X POST $B/v1/sign -H "X-API-Key: $EK" -H "X-API-Secret: $ES" \
    -H "Content-Type: application/json" -d "{\"cpf\":\"12345678909\",\"pdf_base64\":\"$PDF_B64\"}"
done
echo "GET /v1/signatures/count?cpf=12345678909"
curl -s "$B/v1/signatures/count?cpf=12345678909" -H "X-API-Key: $EK" -H "X-API-Secret: $ES"; echo; echo

echo "### 5) historico"
curl -s "$B/v1/signatures?cpf=12345678909" -H "X-API-Key: $EK" -H "X-API-Secret: $ES" | \
  python3 -c "import sys,json;[print(f\"  {s['signed_at'][:19]}  {s['document_name']:<15} {s['status']}  ip={s['ip']}\") for s in json.load(sys.stdin)]"
echo

echo "### 6) validacao do PDF assinado"
python3 -c "
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext
import sys
with open('sb_signed.pdf','rb') as f:
    sig=PdfFileReader(f).embedded_signatures[0]
    st=validate_pdf_signature(sig, ValidationContext(allow_fetching=False))
print('  titular:', sig.signer_cert.subject.human_friendly.split(',')[0])
print('  intacto:', st.intact, '| valido:', st.valid)
" 2>/dev/null
