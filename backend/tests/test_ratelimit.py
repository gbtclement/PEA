from datetime import UTC, datetime, timedelta

from app.services import ratelimit

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_count_is_a_sliding_window(db):
    for minutes in (20, 10, 1):
        ratelimit.record(db, "login_account", "Jean@Example.com", NOW - timedelta(minutes=minutes))
    assert ratelimit.count(db, "login_account", "jean@example.com", NOW) == 2  # 15 min, casse ignorée


def test_over_uses_the_limit_of_the_bucket(db):
    for _ in range(9):
        ratelimit.record(db, "login_account", "jean@example.com", NOW)
    assert not ratelimit.over(db, "login_account", "jean@example.com", NOW)
    ratelimit.record(db, "login_account", "jean@example.com", NOW)
    assert ratelimit.over(db, "login_account", "jean@example.com", NOW)


def test_buckets_and_values_are_separate_and_clear_works(db):
    ratelimit.record(db, "login_account", "a@example.com", NOW)
    ratelimit.record(db, "login_ip", "a@example.com", NOW)
    ratelimit.clear(db, "login_account", "a@example.com")
    assert ratelimit.count(db, "login_account", "a@example.com", NOW) == 0
    assert ratelimit.count(db, "login_ip", "a@example.com", NOW) == 1


def test_values_are_stored_as_hashes_and_purged_after_a_day(db):
    from sqlalchemy import select

    from app.models import RateLimitHit

    ratelimit.record(db, "login_ip", "203.0.113.5", NOW - timedelta(days=2))
    ratelimit.record(db, "login_ip", "203.0.113.5", NOW)
    assert all("203.0.113.5" not in hit.key_hash for hit in db.scalars(select(RateLimitHit)))
    assert ratelimit.purge_hits(db, NOW) == 1
