from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco. SQLite por padrao pra rodar local sem infra.
    # Em producao aponte pro Postgres do Railway:
    # postgresql+psycopg://user:pass@host:5432/db
    database_url: str = "sqlite:///./uniassinatura.db"

    # Chave mestra que criptografa os PFX e senhas em repouso (Fernet, base64 urlsafe 32 bytes).
    # Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    master_key: str

    # Chave de bootstrap pra criar o primeiro cliente admin via /admin/bootstrap.
    bootstrap_token: str = "troque-isto"

    # TSA (carimbo de tempo). Opcional. Se vazio, usa horario do servidor.
    tsa_url: str = ""

    app_name: str = "UNIASSINATURA API"


settings = Settings()
