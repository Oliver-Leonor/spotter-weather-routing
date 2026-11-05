"""Production settings. Every secret and host comes from the environment."""

import os

from .base import *  # noqa: F401,F403
from .base import env_list

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
