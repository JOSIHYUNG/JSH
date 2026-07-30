from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str:
    return request_id_context.get() or f"req_{uuid4().hex}"


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False


class ResponseMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str = Field(default_factory=current_request_id)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pagination: PaginationMeta | None = None
    warnings: list[str] = Field(default_factory=list)


class ApiResponse(BaseModel, Generic[T]):
    data: T | None
    meta: ResponseMeta
    error: ErrorPayload | None = None


def success(data: T, *, pagination: PaginationMeta | None = None, warnings: list[str] | None = None) -> ApiResponse[T]:
    return ApiResponse(data=data, meta=ResponseMeta(pagination=pagination, warnings=warnings or []), error=None)


def failure(error: ErrorPayload, *, request_id: str | None = None) -> ApiResponse[None]:
    meta = ResponseMeta()
    if request_id:
        meta.request_id = request_id
    return ApiResponse(data=None, meta=meta, error=error)


def page_meta(page: int, page_size: int, total_items: int) -> PaginationMeta:
    total_pages = (total_items + page_size - 1) // page_size if total_items else 0
    return PaginationMeta(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )
