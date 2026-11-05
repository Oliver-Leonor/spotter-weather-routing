"""JSON handlers for failures that never reach a DRF view.

URL resolution failures (404) and unhandled exceptions (500) are handled by Django, not DRF, so
without these the API would answer with HTML. Registered as `handler404`/`handler500` in
`config/urls.py`. Django only uses them when DEBUG is False (dev mode shows technical pages).
"""

from django.http import HttpRequest, JsonResponse


def not_found(request: HttpRequest, exception: Exception | None = None) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "NOT_FOUND", "message": f"No API route matches {request.path}."}},
        status=404,
    )


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "SERVER_ERROR", "message": "An unexpected error occurred."}},
        status=500,
    )
