import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Certificate, SignatureLog
from ..security import decrypt_blob, sha256_hex
from ..signing import sign_pdf
from ..deps import get_current_client, check_authorization
from .. import schemas

router = APIRouter(prefix="/v1", tags=["assinatura"])


@router.post("/sign", response_model=schemas.SignResponse)
def sign(body: schemas.SignRequest, request: Request,
         client=Depends(get_current_client), db: Session = Depends(get_db)):
    """Assina um PDF com o certificado do CPF informado. Exige autorizacao 'sign' para o CPF."""
    check_authorization(client, body.cpf, "sign", db)

    cert = db.query(Certificate).filter(Certificate.owner_cpf == body.cpf, Certificate.active == True).first()
    if not cert:
        raise HTTPException(404, f"Sem certificado ativo para o CPF {body.cpf}")
    if cert.not_after and cert.not_after < datetime.utcnow():
        raise HTTPException(422, "Certificado vencido")

    try:
        pdf_bytes = base64.b64decode(body.pdf_base64)
    except Exception:
        raise HTTPException(400, "pdf_base64 invalido")

    doc_hash = sha256_hex(pdf_bytes)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    log = SignatureLog(
        client_id=client.id, certificate_id=cert.id, cpf=body.cpf,
        document_name=body.document_name, document_hash=doc_hash,
        reason=body.reason, location=body.location, ip=ip, user_agent=ua,
    )
    try:
        pfx = decrypt_blob(cert.pfx_encrypted)
        pwd = decrypt_blob(cert.pfx_password_encrypted).decode()
        signed, tsa = sign_pdf(pdf_bytes, pfx, pwd, reason=body.reason, location=body.location)
        signed_hash = sha256_hex(signed)
        log.signed_hash = signed_hash
        log.tsa_used = tsa
        log.status = "ok"
        db.add(log)
        db.commit()
        db.refresh(log)
        return schemas.SignResponse(
            signature_id=log.id, cpf=body.cpf, document_name=body.document_name,
            document_hash=doc_hash, signed_hash=signed_hash,
            signed_pdf_base64=base64.b64encode(signed).decode(),
            tsa_used=tsa, signed_at=log.signed_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        log.status = "error"
        log.error = str(e)[:2000]
        db.add(log)
        db.commit()
        raise HTTPException(500, f"Falha ao assinar: {e}")


@router.get("/signatures", response_model=list[schemas.SignatureLogOut])
def list_signatures(cpf: str, limit: int = 100,
                    client=Depends(get_current_client), db: Session = Depends(get_db)):
    """Lista assinaturas de um CPF. Exige autorizacao 'read'."""
    check_authorization(client, cpf, "read", db)
    q = db.query(SignatureLog).filter(SignatureLog.cpf == cpf)
    if not client.is_admin:
        q = q.filter(SignatureLog.client_id == client.id)
    return q.order_by(SignatureLog.signed_at.desc()).limit(min(limit, 500)).all()


@router.get("/signatures/count", response_model=schemas.SignatureCount)
def count_signatures(cpf: str, client=Depends(get_current_client), db: Session = Depends(get_db)):
    """Quantas vezes assinou (total, ok, erro) e a ultima assinatura. Exige 'read'."""
    check_authorization(client, cpf, "read", db)
    q = db.query(SignatureLog).filter(SignatureLog.cpf == cpf)
    if not client.is_admin:
        q = q.filter(SignatureLog.client_id == client.id)
    total = q.count()
    ok = q.filter(SignatureLog.status == "ok").count()
    last = q.order_by(SignatureLog.signed_at.desc()).first()
    return schemas.SignatureCount(
        cpf=cpf, total=total, ok=ok, error=total - ok,
        last_signed_at=last.signed_at if last else None,
    )
