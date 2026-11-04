from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RUTA_", env_file=".env")

    # Rol de la aplicación: sin BYPASSRLS y sin ser dueño de las tablas.
    database_url: str = "postgresql+psycopg://ruta_app:ruta_app@localhost:5433/ruta"
    # Rol dueño: solo para migraciones.
    admin_database_url: str = "postgresql+psycopg://postgres@localhost:5433/ruta"
    jwt_secret: str = "cambiar-en-produccion-clave-de-32-bytes-minimo"
    jwt_minutes: int = 60
    invitation_days: int = 7
    survey_link_days: int = 14
    storage_dir: str = "storage"
    max_upload_mb: int = 25
    inline_jobs: bool = False  # pruebas: True
    public_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    llm_provider: str = "stub"          # "stub" | "anthropic" (el proveedor autorizado está por decidir)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"


settings = Settings()
