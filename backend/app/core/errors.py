from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainError(Exception):
    code: str
    message: str
    status_code: int = 400
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


def not_found(code: str, message: str) -> DomainError:
    return DomainError(code, message, 404)


def conflict(code: str, message: str, details: dict[str, Any] | None = None) -> DomainError:
    return DomainError(code, message, 409, details=details or {})
