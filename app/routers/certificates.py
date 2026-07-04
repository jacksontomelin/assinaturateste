from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Certificate
from ..security import encrypt_blob
from ..signing import read_pfx_metadata
from ..deps import require_admin
from .. import schemas

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("", response_model=schemas.CertificateOut)
async def upload_certificate(
    cpf: str = Form(...),
    password: str = Form(...),
    pfx: UploadFile = File(...),
    _=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Registra um PFX sob custodia, atrelado ao CPF. Somente admin."""
    pfx_bytes = await pfx.read()
    try:
        meta = read_pfx_metadata(pfx_bytes, password)
    except Exception:
        raise HTTPException(400, "PFX invalido ou senha incorreta")

    # desativa certs antigos do mesmo CPF
    db.query(Certificate).filter(Certificate.owner_cpf == cpf, Certificate.active == True).update({"active": False})

    cert = Certificate(
        owner_cpf=cpf.strip(),
        owner_name=meta["owner_name"],
        pfx_encrypted=encrypt_blob(pfx_bytes),
        pfx_password_encrypted=encrypt_blob(password.encode()),
        thumbprint=meta["thumbprint"],
        not_before=meta["not_before"],
        not_after=meta["not_after"],
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return _to_out(cert)


@router.get("", response_model=list[schemas.CertificateOut])
def list_certificates(_=Depends(require_admin), db: Session = Depends(get_db)):
    return [_to_out(c) for c in db.query(Certificate).order_by(Certificate.created_at.desc()).all()]


@router.get("/{cpf}", response_model=schemas.CertificateOut)
def get_by_cpf(cpf: str, _=Depends(require_admin), db: Session = Depends(get_db)):
    cert = db.query(Certificate).filter(Certificate.owner_cpf == cpf, Certificate.active == True).first()
    if not cert:
        raise HTTPException(404, "Certificado ativo nao encontrado para esse CPF")
    return _to_out(cert)


def _to_out(cert: Certificate) -> schemas.CertificateOut:
    out = schemas.CertificateOut.model_validate(cert)
    out.expired = bool(cert.not_after and cert.not_after < datetime.utcnow())
    return out
