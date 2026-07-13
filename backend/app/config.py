from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "高级统计课程知识图谱学习路径推荐系统"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./backend/data/app.db"
    jwt_secret: str = "development-only-secret"
    jwt_expire_minutes: int = 480
    frontend_origin: str = "http://127.0.0.1:5173"

    @field_validator("database_url")
    @classmethod
    def normalize_sqlite_url(cls, value: str) -> str:
        prefix = "sqlite:///"
        if not value.startswith(prefix) or value == "sqlite:///:memory:":
            return value
        path = Path(value.removeprefix(prefix))
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return f"{prefix}{path.resolve().as_posix()}"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
