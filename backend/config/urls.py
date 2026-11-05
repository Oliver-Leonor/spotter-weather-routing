from django.urls import include, path

urlpatterns = [
    path("api/", include("analysis.urls")),
]

# Unresolved paths and unhandled exceptions never reach DRF; keep the JSON error envelope.
handler404 = "analysis.errors.not_found"
handler500 = "analysis.errors.server_error"
