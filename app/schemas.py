from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# --- clientes externos ---
class ClientCreate(BaseModel):
    name: str
    is_admin: bool = False


class ClientCredentials(BaseModel):
    id: str
    name: str
    api_key: str
    api_secret: str  # mostrado UMA vez, na criacao
    is_admin: bool


class ClientOut(BaseModel):
    id: str
    name: str
    api_key: str
    is_admin: bool
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- certificados ---
class CertificateOut(BaseModel):
    id: str
    owner_cpf: str
    owner_name: str
    thumbprint: Optional[str]
    not_before: Optional[datetime]
    not_after: Optional[datetime]
    active: bool
    expired: bool = False

    class Config:
        from_attributes = True


# --- autorizacoes ---
class AuthorizationCreate(BaseModel):
    client_id: str
    cpf: str
    can_sign: bool = True
    can_read: bool = True
    expires_at: Optional[datetime] = None


class AuthorizationOut(BaseModel):
    id: str
    client_id: str
    cpf: str
    can_sign: bool
    can_read: bool
    active: bool
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


# --- assinatura ---
class SignRequest(BaseModel):
    cpf: str
    pdf_base64: str
    document_name: Optional[str] = "documento.pdf"
    reason: Optional[str] = "Assinatura digital"
    location: Optional[str] = "Blumenau/SC"


class SignResponse(BaseModel):
    signature_id: str
    cpf: str
    document_name: str
    document_hash: str
    signed_hash: str
    signed_pdf_base64: str
    tsa_used: bool
    signed_at: datetime


class SignatureLogOut(BaseModel):
    id: str
    cpf: str
    document_name: Optional[str]
    document_hash: Optional[str]
    reason: Optional[str]
    ip: Optional[str]
    tsa_used: bool
    status: str
    signed_at: datetime

    class Config:
        from_attributes = True


class SignatureCount(BaseModel):
    cpf: str
    total: int
    ok: int
    error: int
    last_signed_at: Optional[datetime]
