from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.envelope import request_id_context
from app.core.errors import DomainError
from app.core.http import domain_error_handler, unexpected_error_handler, validation_error_handler
from app.db import init_database
from app.services.jobs import recover_interrupted_jobs, recover_interrupted_questions


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_database()
    recover_interrupted_jobs()
    recover_interrupted_questions()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
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


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "").strip()
    request_id = supplied[:128] if supplied else f"req_{uuid4().hex}"
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith(f"{settings.api_v1_prefix}/documents/") and request.url.path.endswith("/original"):
            response.headers["Cache-Control"] = "no-store"
        elif request.url.path.startswith(f"{settings.api_v1_prefix}/questions"):
            response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        request_id_context.reset(token)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"message": "JSH Second Brain API is running", "docs": "/docs"}


@app.get("/health", tags=["system"])
def legacy_health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
