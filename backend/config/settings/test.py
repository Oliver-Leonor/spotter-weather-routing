from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
ALLOW_FIXTURE_MODE = True
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
