from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config. Every value is overridable via environment variable
    (case-insensitive), never hardcoded — this is what lets the same image
    run against MySQL in prod and SQLite in tests/CI without code changes.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:rootpass@db:3306/servicepulse"
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()
