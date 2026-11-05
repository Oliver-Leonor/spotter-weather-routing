import pytest


@pytest.fixture(autouse=True)
def _isolated_provider_caches():
    """Provider responses are cached in-process; no test may see another test's responses."""
    from routing.providers.valhalla import ROUTE_CACHE
    from weather.geocoding import GEOCODE_CACHE
    from weather.open_meteo import FORECAST_CACHE

    caches = (ROUTE_CACHE, FORECAST_CACHE, GEOCODE_CACHE)
    for cache in caches:
        cache.clear()
    yield
    for cache in caches:
        cache.clear()
