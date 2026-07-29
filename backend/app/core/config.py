from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JSH Second Brain API"
    app_version: str = "0.2.0"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/app.db"
    storage_root: Path = Path("./data/storage")
    openai_api_key: str | None = None
    openai_vector_store_id: str | None = None
    openai_chat_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    max_upload_bytes: int = 20_000_000
    analysis_timeout_seconds: int = 300
    question_timeout_seconds: int = 90
    graph_node_limit: int = 500
    graph_edge_limit: int = 1_500
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    analysis_poll_interval_seconds: float = 0.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw = self.database_url[len(prefix):]
        return Path(raw[2:] if raw.startswith("./") else raw)


@lru_cache
def get_settings() -> Settings:
    return Settings()
