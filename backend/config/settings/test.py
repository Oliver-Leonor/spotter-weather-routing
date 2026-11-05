from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
ALLOW_FIXTURE_MODE = True
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    # A rate of None switches a throttle off; the rate limit has its own test.
    "DEFAULT_THROTTLE_RATES": {"anon": None, "analyze": None, "geocode": None},
}
