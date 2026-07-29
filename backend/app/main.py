from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.http import domain_error_handler, unexpected_error_handler, validation_error_handler
from app.db import init_database


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"message": "JSH Second Brain API is running", "docs": "/docs"}


@app.get("/health", tags=["system"])
def legacy_health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
