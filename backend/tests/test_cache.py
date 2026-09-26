from app.services.cache import TTLCache


def test_cache_reuses_value_until_expiry():
    now = [0.0]
    cache = TTLCache(60, clock=lambda: now[0])
    calls = []
    factory = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert cache.get_or_set("k", factory) == 1
    now[0] = 59
    assert cache.get_or_set("k", factory) == 1
    now[0] = 61
    assert cache.get_or_set("k", factory) == 2


def test_cache_clear():
    cache = TTLCache(60)
    cache.get_or_set("k", lambda: 1)
    cache.clear()
    assert cache.get_or_set("k", lambda: 2) == 2
