from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import ApiClient, Authorization
from ..security import gen_api_key, gen_secret, hash_secret
from ..config import settings
from ..deps import require_admin
from .. import schemas

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/bootstrap", response_model=schemas.ClientCredentials)
def bootstrap(x_bootstrap_token: str = Header(..., alias="X-Bootstrap-Token"), db: Session = Depends(get_db)):
    """Cria o primeiro cliente admin. So funciona se nao existir nenhum admin ainda."""
    if x_bootstrap_token != settings.bootstrap_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bootstrap token invalido")
    if db.query(ApiClient).filter(ApiClient.is_admin == True).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Ja existe um admin")
    return _create_client(db, "admin", is_admin=True)


@router.post("/clients", response_model=schemas.ClientCredentials)
def create_client(body: schemas.ClientCreate, _=Depends(require_admin), db: Session = Depends(get_db)):
    return _create_client(db, body.name, body.is_admin)


@router.get("/clients", response_model=list[schemas.ClientOut])
def list_clients(_=Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(ApiClient).order_by(ApiClient.created_at.desc()).all()


@router.post("/clients/{client_id}/deactivate")
def deactivate_client(client_id: str, _=Depends(require_admin), db: Session = Depends(get_db)):
    c = db.get(ApiClient, client_id)
    if not c:
        raise HTTPException(404, "Cliente nao encontrado")
    c.active = False
    db.commit()
    return {"ok": True}


@router.post("/authorizations", response_model=schemas.AuthorizationOut)
def grant(body: schemas.AuthorizationCreate, _=Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(ApiClient, body.client_id):
        raise HTTPException(404, "Cliente nao encontrado")
    auth = Authorization(
        client_id=body.client_id, cpf=body.cpf.strip(),
        can_sign=body.can_sign, can_read=body.can_read, expires_at=body.expires_at,
    )
    db.add(auth)
    db.commit()
    db.refresh(auth)
    return auth


@router.get("/authorizations", response_model=list[schemas.AuthorizationOut])
def list_authorizations(client_id: str | None = None, _=Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(Authorization)
    if client_id:
        q = q.filter(Authorization.client_id == client_id)
    return q.order_by(Authorization.created_at.desc()).all()


@router.post("/authorizations/{auth_id}/revoke")
def revoke(auth_id: str, _=Depends(require_admin), db: Session = Depends(get_db)):
    a = db.get(Authorization, auth_id)
    if not a:
        raise HTTPException(404, "Autorizacao nao encontrada")
    a.active = False
    db.commit()
    return {"ok": True}


def _create_client(db: Session, name: str, is_admin: bool) -> schemas.ClientCredentials:
    api_key = gen_api_key()
    secret = gen_secret()
    client = ApiClient(name=name, api_key=api_key, secret_hash=hash_secret(secret), is_admin=is_admin)
    db.add(client)
    db.commit()
    db.refresh(client)
    return schemas.ClientCredentials(
        id=client.id, name=client.name, api_key=api_key, api_secret=secret, is_admin=is_admin
    )
