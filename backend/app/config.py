from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config. Every value is overridable via environment variable
    (case-insensitive), never hardcoded — this is what lets the same image
    run against MySQL in prod and SQLite in tests/CI without code changes.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:rootpass@db:3306/servicepulse"
    db_host: Optional[str] = None
    db_port: int = 3306
    db_name: str = "servicepulse"
    db_user: str = "admin"
    db_password: Optional[str] = None
    environment: str = "development"
    log_level: str = "INFO"

    def model_post_init(self, __context) -> None:
        # En prod (ECS), le mot de passe arrive via un "secrets" (lu en
        # direct depuis Secrets Manager), jamais en variable d'environnement
        # en clair — donc l'URL complète ne peut pas être transmise d'un
        # bloc. Quand les morceaux séparés sont présents, on la construit ici.
        if self.db_host and self.db_password:
            self.database_url = (
                f"mysql+pymysql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )


settings = Settings()
