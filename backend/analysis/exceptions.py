"""Uniform JSON error envelope: {"error": {"code": ..., "message": ..., "details": ...}}."""

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


class UpstreamError(Exception):
    """Raised by provider clients; mapped to 502/504 by the API layer."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "UPSTREAM_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        code: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


def exception_handler(exc, context):
    from rest_framework.response import Response

    if isinstance(exc, UpstreamError):
        return Response(
            {"error": {"code": exc.code, "message": exc.message, "provider": exc.provider}},
            status=exc.status_code,
        )
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, ValidationError):
        response.data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request.",
                "details": exc.detail,
            }
        }
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else response.data
        response.data = {"error": {"code": exc.__class__.__name__.upper(), "message": str(detail)}}
    return response
