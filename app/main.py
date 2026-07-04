import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError, ProgrammingError
from .config import settings
from .database import Base, engine
from .routers import admin, certificates, signatures

log = logging.getLogger("uniassinatura")


def init_db():
    # checkfirst evita recriar; try/except cobre a corrida entre workers no boot
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
    version="1.0.0",
    description="API de custodia de PFX e assinatura digital PAdES com controle por CPF e autorizacao.",
    lifespan=lifespan,
)

app.include_router(admin.router)
app.include_router(certificates.router)
app.include_router(signatures.router)


@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "app": settings.app_name}
