"""Base Django settings for StormRoute.

No database, no auth, no sessions: the app is a stateless API in front of routing and weather
providers. Environment variables are read from the process (and from a repo-root `.env` in dev).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env", override=False)

APP_VERSION = "0.1.0"


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "risk",
    "analysis",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES: dict = {}

STATIC_URL = "static/"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": os.environ.get("API_THROTTLE_RATE", "60/min")},
    "EXCEPTION_HANDLER": "analysis.exceptions.exception_handler",
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = False

# Provider configuration (no secrets; see .env.example)
ROUTING_PROVIDER = os.environ.get("ROUTING_PROVIDER", "valhalla")
VALHALLA_BASE_URL = os.environ.get("VALHALLA_BASE_URL", "https://valhalla1.openstreetmap.de")
VALHALLA_COSTING = os.environ.get("VALHALLA_COSTING", "auto")
OPEN_METEO_BASE_URL = os.environ.get("OPEN_METEO_BASE_URL", "https://api.open-meteo.com")
OPEN_METEO_GEOCODING_URL = os.environ.get(
    "OPEN_METEO_GEOCODING_URL", "https://geocoding-api.open-meteo.com"
)
APP_CONTACT_EMAIL = os.environ.get("APP_CONTACT_EMAIL", "")
ALLOW_FIXTURE_MODE = env_bool("ALLOW_FIXTURE_MODE", True)
UPSTREAM_TIMEOUT_SECONDS = float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "25"))
USER_AGENT = (
    f"StormRoute/{APP_VERSION} (+https://github.com/Oliver-Leonor/spotter-weather-routing"
    + (f"; {APP_CONTACT_EMAIL})" if APP_CONTACT_EMAIL else ")")
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
