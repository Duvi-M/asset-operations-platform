from functools import lru_cache
from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://asset_ops_user:asset_ops_pass@db:5432/asset_ops_db"
    auto_create_tables: bool = False

    # App
    app_name: str = "Asset Operations Platform"
    app_version: str = "0.1.0"
    debug: bool = False
    media_dir: str = "/app/media"
    auth_secret_key: str = "change-me-in-production"
    access_token_exp_minutes: int = 60 * 12
    auth_issuer: str = "asset-operations-platform"

    # Cloudinary — si no está configurado, se usa almacenamiento local (dev)
    # Formato: cloudinary://api_key:api_secret@cloud_name
    cloudinary_url: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Normalize database URLs for SQLAlchemy.

        Render may provide DATABASE_URL using the postgres:// scheme, while
        SQLAlchemy expects postgresql://.
        """
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql://", 1)
        return self.database_url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def using_default_auth_secret(self) -> bool:
        return self.auth_secret_key == "change-me-in-production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_default_local_database(self) -> bool:
        return self.database_url == "postgresql://asset_ops_user:asset_ops_pass@db:5432/asset_ops_db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
