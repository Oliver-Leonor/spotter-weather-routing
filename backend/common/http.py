"""Outbound HTTP for the provider clients: one shared client and uniform failure mapping."""

from __future__ import annotations

import threading
from typing import Any

import httpx
from django.conf import settings

from .errors import UpstreamError

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _shared_client() -> httpx.Client:
    """Created on first use so connections are reused for the life of the process."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(
                headers={"User-Agent": settings.USER_AGENT},
                timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
            )
        return _client


def send(
    method: str,
    url: str,
    *,
    provider: str,
    unavailable_code: str,
    timeout_code: str,
    **request_kwargs: Any,
) -> httpx.Response:
    """Send a request and return the response, whatever its status.

    A timeout becomes a 504 and is not retried. A failed connection is retried once and then
    becomes a 502, as does any other transport error.
    """
    connection_attempts = 0
    while True:
        try:
            return _shared_client().request(method, url, **request_kwargs)
        except httpx.TimeoutException as exc:
            raise UpstreamError(
                f"The {provider} service did not respond in time. Please try again.",
                provider=provider,
                code=timeout_code,
                status_code=504,
            ) from exc
        except httpx.ConnectError as exc:
            connection_attempts += 1
            if connection_attempts > 1:
                raise _unavailable(provider, unavailable_code, "could not be reached") from exc
        except httpx.HTTPError as exc:
            raise _unavailable(provider, unavailable_code, "could not be reached") from exc


def read_json(response: httpx.Response, *, provider: str, unavailable_code: str) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise _unavailable(provider, unavailable_code, "returned an unreadable response") from exc


def _unavailable(provider: str, code: str, problem: str) -> UpstreamError:
    return UpstreamError(
        f"The {provider} service {problem}. Please try again shortly.",
        provider=provider,
        code=code,
    )
