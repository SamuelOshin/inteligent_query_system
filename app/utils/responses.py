"""
utils/responses.py

Single source of truth for all API response shapes.
Every route and exception handler calls these — never constructs
{"status": ...} dicts manually anywhere else in the codebase.
"""

from typing import Any
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_response(data: Any, status_code: int = 200) -> JSONResponse:
    """
    Wraps a single resource in the standard success envelope.

    Shape:
        {"status": "success", "data": {...}}
    """
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"status": "success", "data": data}),
    )


def success_list_response(
    data: list,
    total: int,
    page: int,
    limit: int,
    status_code: int = 200,
) -> JSONResponse:
    """
    Wraps a paginated list in the standard success envelope.

    Shape:
        {"status": "success", "page": 1, "limit": 10, "total": 2026, "data": [...]}
    """
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            "status": "success",
            "page": page,
            "limit": limit,
            "total": total,
            "data": data,
        }),
    )


def error_response(message: str, status_code: int) -> JSONResponse:
    """
    Wraps an error message in the standard error envelope.

    Shape:
        {"status": "error", "message": "..."}
    """
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"status": "error", "message": message}),
    )
