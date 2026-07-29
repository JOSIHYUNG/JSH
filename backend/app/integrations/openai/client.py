from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI | None:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
