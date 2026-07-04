import io
import os
import tempfile
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12
from pyhanko.sign import signers
from pyhanko.sign.signers.pdf_signer import PdfSigner
from pyhanko.sign.timestamps import HTTPTimeStamper
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from .config import settings


def read_pfx_metadata(pfx_bytes: bytes, password: str) -> dict:
    """Le validade, titular e thumbprint do PFX sem assinar nada."""
    _key, cert, _extra = pkcs12.load_key_and_certificates(pfx_bytes, password.encode())
    thumb = cert.fingerprint(hashes.SHA256()).hex()
    cn = ""
    for attr in cert.subject:
        if attr.oid._name in ("commonName", "2.5.4.3"):
            cn = attr.value
    return {
        "owner_name": cn,
        "not_before": cert.not_valid_before_utc.replace(tzinfo=None),
        "not_after": cert.not_valid_after_utc.replace(tzinfo=None),
        "thumbprint": thumb,
    }


def _load_signer(pfx_bytes: bytes, password: str):
    with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as tmp:
        tmp.write(pfx_bytes)
        path = tmp.name
    try:
        return signers.SimpleSigner.load_pkcs12(path, passphrase=password.encode())
    finally:
        os.unlink(path)


def sign_pdf(pdf_bytes: bytes, pfx_bytes: bytes, password: str,
             reason: str = "Assinatura digital", location: str = "") -> tuple[bytes, bool]:
    """Assina o PDF (PAdES). Retorna (pdf_assinado, usou_tsa)."""
    signer = _load_signer(pfx_bytes, password)

    timestamper = None
    used_tsa = False
    if settings.tsa_url:
        timestamper = HTTPTimeStamper(url=settings.tsa_url)
        used_tsa = True

    meta = signers.PdfSignatureMetadata(
        field_name=f"Sig_{int(datetime.utcnow().timestamp())}",
        reason=reason,
        location=location,
    )
    pdf_signer = PdfSigner(meta, signer=signer, timestamper=timestamper)

    out = io.BytesIO()
    w = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    pdf_signer.sign_pdf(w, output=out)
    return out.getvalue(), used_tsa
