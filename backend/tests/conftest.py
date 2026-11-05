import pytest


@pytest.fixture(autouse=True)
def _isolated_provider_caches():
    """Provider responses are cached in-process; no test may see another test's responses."""
    from routing.providers.valhalla import ROUTE_CACHE

    ROUTE_CACHE.clear()
    yield
    ROUTE_CACHE.clear()
