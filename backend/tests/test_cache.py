"""In-process TTL cache used for provider responses."""

from common.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_returns_a_stored_value_until_it_expires():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=60, clock=clock)
    cache.set("k", "value")

    clock.now += 59
    assert cache.get("k") == "value"
    clock.now += 2
    assert cache.get("k") is None


def test_missing_key_returns_none():
    assert TTLCache(ttl_seconds=60).get("absent") is None


def test_oldest_entry_is_evicted_when_full():
    cache = TTLCache(ttl_seconds=60, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert (cache.get("b"), cache.get("c")) == (2, 3)


def test_expired_entries_are_dropped_before_live_ones():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=60, max_entries=2, clock=clock)
    cache.set("old", 1)
    clock.now += 30
    cache.set("live", 2)
    clock.now += 40  # "old" has expired, "live" has not
    cache.set("new", 3)
    assert cache.get("old") is None
    assert (cache.get("live"), cache.get("new")) == (2, 3)


def test_clear_empties_the_cache():
    cache = TTLCache(ttl_seconds=60)
    cache.set("k", "value")
    cache.clear()
    assert cache.get("k") is None
