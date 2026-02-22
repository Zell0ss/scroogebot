from __future__ import annotations
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_apikey: str
    telegram_name: str
    telegram_username: str
    anthropic_apikey: str = ""

    mariadb_host: str = "localhost"
    mariadb_port: int = 3306
    mariadb_database: str
    mariadb_user: str
    mariadb_password: str

    @property
    def database_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mariadb_user}:{self.mariadb_password}"
            f"@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_database}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.mariadb_user}:{self.mariadb_password}"
            f"@{self.mariadb_host}:{self.mariadb_port}/{self.mariadb_database}"
        )


def load_app_config(path: str = "config/config.yaml") -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f)


settings = Settings()
app_config = load_app_config()
