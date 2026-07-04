"""
Demo self-contained da UNIASSINATURA API.

Roda tudo em memoria (sem subir servidor, sem infra):
- gera um PFX de teste self-signed pro CPF 12345678909
- gera um PDF de teste
- executa: bootstrap admin -> upload PFX -> cria cliente externo ->
  bloqueio sem autorizacao -> grant -> assinatura -> contagem -> historico
- valida a assinatura do PDF gerado

Uso:
    python demo.py
"""
import os
import base64
import datetime

# --- configura ambiente antes de importar a app ---
os.environ.setdefault(
    "MASTER_KEY",
    __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode(),
)
os.environ["BOOTSTRAP_TOKEN"] = "demo-token"
os.environ["DATABASE_URL"] = "sqlite:///./demo.db"
if os.path.exists("demo.db"):
    os.remove("demo.db")


def build_test_assets():
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
        x509.NameAttribute(NameOID.COMMON_NAME, "JACKSON TOMELIN:12345678909"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        b"demo", key, cert, None, serialization.BestAvailableEncryption(b"senha123")
    )

    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "Procuracao de teste - UNIPROCURACOES")
    c.save()
    return pfx, buf.getvalue()


def main():
    pfx_bytes, pdf_bytes = build_test_assets()

    from fastapi.testclient import TestClient
    from app.main import app
    api = TestClient(app)

    def h(k, s):
        return {"X-API-Key": k, "X-API-Secret": s}

    def line(t):
        print("\n" + "=" * 4, t)

    CPF = "12345678909"

    line("1. Bootstrap admin")
    r = api.post("/admin/bootstrap", headers={"X-Bootstrap-Token": "demo-token"})
    adm = r.json(); AK, AS = adm["api_key"], adm["api_secret"]
    print(f"   {r.status_code}  admin criado  key={AK[:14]}...")

    line("2. Upload do PFX -> CPF " + CPF)
    r = api.post("/certificates", headers=h(AK, AS),
                 data={"cpf": CPF, "password": "senha123"},
                 files={"pfx": ("cert.pfx", pfx_bytes, "application/x-pkcs12")})
    j = r.json()
    print(f"   {r.status_code}  titular={j['owner_name']}")
    print(f"        validade ate {j['not_after']}  vencido={j['expired']}")

    line("3. Cria cliente externo (sistema parceiro)")
    r = api.post("/admin/clients", headers=h(AK, AS), json={"name": "Sistema Parceiro X"})
    ext = r.json(); EK, ES = ext["api_key"], ext["api_secret"]
    print(f"   {r.status_code}  cliente={ext['name']}  key={EK[:14]}...")

    line("4. Externo tenta assinar SEM autorizacao (esperado: 403)")
    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    r = api.post("/v1/sign", headers=h(EK, ES), json={"cpf": CPF, "pdf_base64": pdf_b64})
    print(f"   {r.status_code}  {r.json()['detail']}")

    line("5. Admin autoriza o externo pelo CPF")
    r = api.post("/admin/authorizations", headers=h(AK, AS),
                 json={"client_id": ext["id"], "cpf": CPF, "can_sign": True, "can_read": True})
    print(f"   {r.status_code}  grant criado")

    line("6. Externo assina COM autorizacao")
    r = api.post("/v1/sign", headers=h(EK, ES),
                 json={"cpf": CPF, "pdf_base64": pdf_b64, "document_name": "procuracao.pdf"})
    res = r.json()
    print(f"   {r.status_code}  signature_id={res['signature_id'][:14]}...  tsa={res['tsa_used']}")
    print(f"        hash doc      = {res['document_hash']}")
    print(f"        hash assinado = {res['signed_hash']}")
    with open("demo_signed.pdf", "wb") as f:
        f.write(base64.b64decode(res["signed_pdf_base64"]))
    print("        PDF assinado salvo em demo_signed.pdf")

    line("7. Assina mais 2x")
    for _ in range(2):
        api.post("/v1/sign", headers=h(EK, ES), json={"cpf": CPF, "pdf_base64": pdf_b64})
    print("   ok")

    line("8. Quantas vezes assinou pelo CPF")
    r = api.get("/v1/signatures/count", headers=h(EK, ES), params={"cpf": CPF})
    print(f"   {r.status_code}  {r.json()}")

    line("9. Historico")
    r = api.get("/v1/signatures", headers=h(EK, ES), params={"cpf": CPF})
    for s in r.json():
        print(f"   {s['signed_at'][:19]}  {s['document_name']:<16} {s['status']}  ip={s['ip']}")

    line("10. Validacao criptografica do PDF assinado")
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    with open("demo_signed.pdf", "rb") as f:
        sig = PdfFileReader(f).embedded_signatures[0]
        st = validate_pdf_signature(sig, ValidationContext(allow_fetching=False))
    print(f"   titular no PDF: {sig.signer_cert.subject.human_friendly.split(',')[0]}")
    print(f"   intacto={st.intact}  valido={st.valid}  (untrusted e' esperado: cert self-signed de teste)")

    print("\nOK. Fluxo completo funcionando.")


if __name__ == "__main__":
    main()
