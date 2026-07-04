from datetime import datetime
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from .models import ApiClient, Authorization
from .security import verify_secret


def get_current_client(
    x_api_key: str = Header(..., alias="X-API-Key"),
    x_api_secret: str = Header(..., alias="X-API-Secret"),
    db: Session = Depends(get_db),
) -> ApiClient:
    client = db.query(ApiClient).filter(ApiClient.api_key == x_api_key, ApiClient.active == True).first()
    if not client or not verify_secret(x_api_secret, client.secret_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais invalidas")
    return client


def require_admin(client: ApiClient = Depends(get_current_client)) -> ApiClient:
    if not client.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requer cliente admin")
    return client


def check_authorization(client: ApiClient, cpf: str, action: str, db: Session) -> Authorization:
    """action = 'sign' ou 'read'. Admin passa direto."""
    if client.is_admin:
        return None
    auth = (
        db.query(Authorization)
        .filter(Authorization.client_id == client.id, Authorization.cpf == cpf, Authorization.active == True)
        .first()
    )
    if not auth:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Cliente sem autorizacao para o CPF {cpf}")
    if auth.expires_at and auth.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorizacao expirada")
    if action == "sign" and not auth.can_sign:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorizacao nao permite assinar")
    if action == "read" and not auth.can_read:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorizacao nao permite consultar")
    return auth
