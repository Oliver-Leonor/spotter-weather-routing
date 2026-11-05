"""Uniform JSON error envelope: {"error": {"code": ..., "message": ..., ...}}."""

from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.errors import AppError


def exception_handler(exc, context):
    if isinstance(exc, AppError):
        error = {"code": exc.code, "message": exc.message}
        if exc.provider:
            error["provider"] = exc.provider
        return Response({"error": error}, status=exc.status_code)

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
