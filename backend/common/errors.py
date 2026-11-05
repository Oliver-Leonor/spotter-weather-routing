"""Expected failures, each with a stable API error code and HTTP status.

Raised by the provider clients and the analysis service; rendered as the JSON error envelope by
`analysis.exceptions.exception_handler`.
"""

from __future__ import annotations


class AppError(Exception):
    status_code = 500
    code = "SERVER_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        provider: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.provider = provider
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class UpstreamError(AppError):
    """A routing, weather or geocoding provider failed (502) or timed out (504)."""

    status_code = 502
    code = "UPSTREAM_ERROR"

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        code: str | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message, code=code, status_code=status_code, provider=provider)


class NoRouteError(AppError):
    """The routing provider answered, but there is no drivable route for this trip."""

    status_code = 422
    code = "NO_ROUTE"


class TripTooLargeError(AppError):
    """The trip needs more forecast points than one analysis may request from the weather API."""

    status_code = 422
    code = "TRIP_TOO_LARGE"
