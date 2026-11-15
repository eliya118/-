from enum import StrEnum

from pydantic import BaseModel


class ErrorCode(StrEnum):
    unauthenticated = "unauthenticated"
    validation_error = "validation_error"
    not_found = "not_found"
    rate_limited = "rate_limited"
    upstream_unavailable = "upstream_unavailable"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_payload(code: ErrorCode, message: str, request_id: str) -> dict[str, object]:
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id)
    ).model_dump()
