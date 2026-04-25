from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://sgoi_user:sgoi_pass@db:5432/sgoi_db"

    # App
    app_name: str = "SGOI - Sistema de Gestión Operativa e Inventario"
    app_version: str = "0.1.0"
    debug: bool = True
    media_dir: str = "/app/media"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
