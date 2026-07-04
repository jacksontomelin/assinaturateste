import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, LargeBinary, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship
from .database import Base


def _id():
    return uuid.uuid4().hex


class ApiClient(Base):
    """Sistema externo que consome a API."""
    __tablename__ = "api_clients"

    id = Column(String, primary_key=True, default=_id)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)  # id publico
    secret_hash = Column(String, nullable=False)                       # bcrypt do secret
    is_admin = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    authorizations = relationship("Authorization", back_populates="client", cascade="all, delete-orphan")


class Certificate(Base):
    """Certificado A1 (PFX) sob custodia, atrelado ao CPF do titular."""
    __tablename__ = "certificates"

    id = Column(String, primary_key=True, default=_id)
    owner_cpf = Column(String, index=True, nullable=False)
    owner_name = Column(String, nullable=False)
    pfx_encrypted = Column(LargeBinary, nullable=False)       # PFX criptografado (Fernet)
    pfx_password_encrypted = Column(LargeBinary, nullable=False)
    thumbprint = Column(String, index=True)                  # SHA-256 do cert
    not_before = Column(DateTime)
    not_after = Column(DateTime)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_cert_cpf_active", "owner_cpf", "active"),)


class Authorization(Base):
    """Grant: quais CPFs um cliente externo pode usar e pra que (sign / read)."""
    __tablename__ = "authorizations"

    id = Column(String, primary_key=True, default=_id)
    client_id = Column(String, ForeignKey("api_clients.id"), nullable=False)
    cpf = Column(String, index=True, nullable=False)
    can_sign = Column(Boolean, default=True)
    can_read = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)  # opcional
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("ApiClient", back_populates="authorizations")

    __table_args__ = (Index("ix_auth_client_cpf", "client_id", "cpf"),)


class SignatureLog(Base):
    """Auditoria: um registro por tentativa de assinatura."""
    __tablename__ = "signature_logs"

    id = Column(String, primary_key=True, default=_id)
    client_id = Column(String, ForeignKey("api_clients.id"), index=True)
    certificate_id = Column(String, ForeignKey("certificates.id"), index=True, nullable=True)
    cpf = Column(String, index=True)
    document_name = Column(String)
    document_hash = Column(String, index=True)     # SHA-256 do PDF original
    signed_hash = Column(String)                   # SHA-256 do PDF assinado
    reason = Column(String)
    location = Column(String)
    ip = Column(String)
    user_agent = Column(String)
    tsa_used = Column(Boolean, default=False)
    status = Column(String, default="ok")          # ok | error
    error = Column(Text, nullable=True)
    signed_at = Column(DateTime, default=datetime.utcnow, index=True)
