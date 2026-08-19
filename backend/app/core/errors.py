from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details or {}},
        )


def not_found(resource: str, resource_id: str) -> AppError:
    return AppError(
        status.HTTP_404_NOT_FOUND,
        "RESOURCE_NOT_FOUND",
        f"{resource}不存在",
        {"id": resource_id},
    )


def conflict(code: str, message: str, **details: Any) -> AppError:
    return AppError(status.HTTP_409_CONFLICT, code, message, details)


def bad_request(code: str, message: str, **details: Any) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, code, message, details)
