import secrets
import hashlib
import bcrypt
from cryptography.fernet import Fernet
from .config import settings

_fernet = Fernet(settings.master_key.encode())


# --- criptografia em repouso (PFX + senha do PFX) ---
def encrypt_blob(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt_blob(token: bytes) -> bytes:
    return _fernet.decrypt(token)


# --- credenciais do cliente externo ---
def gen_api_key() -> str:
    return "uak_" + secrets.token_urlsafe(18)


def gen_secret() -> str:
    return "usk_" + secrets.token_urlsafe(32)


def _prehash(secret: str) -> bytes:
    # sha256 em hex (64 bytes) evita o limite de 72 bytes do bcrypt de forma segura
    return hashlib.sha256(secret.encode()).hexdigest().encode()


def hash_secret(secret: str) -> str:
    return bcrypt.hashpw(_prehash(secret), bcrypt.gensalt()).decode()


def verify_secret(secret: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(secret), hashed.encode())
    except Exception:
        return False


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
