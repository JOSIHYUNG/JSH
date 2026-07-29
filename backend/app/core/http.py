from collections.abc import Callable
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.envelope import ErrorPayload, failure
from app.core.errors import DomainError


def get_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", f"req_{uuid4().hex}")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    payload = failure(ErrorPayload(code=exc.code, message=exc.message, details=exc.details, retryable=exc.retryable), request_id=get_request_id(request))
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"), headers={"X-Request-ID": payload.meta.request_id})


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = failure(ErrorPayload(code="VALIDATION_ERROR", message="요청 값이 올바르지 않습니다.", details={"issues": exc.errors()}, retryable=False), request_id=get_request_id(request))
    return JSONResponse(status_code=422, content=payload.model_dump(mode="json"), headers={"X-Request-ID": payload.meta.request_id})


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    payload = failure(ErrorPayload(code="INTERNAL_ERROR", message="서버에서 처리하지 못했습니다.", retryable=True), request_id=get_request_id(request))
    return JSONResponse(status_code=500, content=payload.model_dump(mode="json"), headers={"X-Request-ID": payload.meta.request_id})
