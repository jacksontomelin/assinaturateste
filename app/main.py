import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlalchemy.exc import OperationalError, ProgrammingError
from .config import settings
from .database import Base, engine
from .routers import admin, certificates, signatures

log = logging.getLogger("uniassinatura")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def init_db():
    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except (OperationalError, ProgrammingError) as e:
        log.warning("init_db: tabelas ja existiam (corrida entre workers): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.1.0",
    description="API de custodia de PFX e assinatura digital PAdES com controle por CPF e autorizacao.",
    lifespan=lifespan,
)

app.include_router(admin.router)
app.include_router(certificates.router)
app.include_router(signatures.router)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "app": settings.app_name}
