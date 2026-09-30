from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import SecurityEvent
from app.services.security_log import log_event, purge_events
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_event_keeps_only_the_network_of_the_ip(db):
    user = make_user(db, "jean@example.com")
    log_event(db, "login_failed", now=NOW, user_id=user.id, ip="203.0.113.77", details={"method": "password"})
    event = db.scalars(select(SecurityEvent)).one()
    assert (event.kind, event.user_id, event.ip, event.details) == ("login_failed", user.id, "203.0.113.0/24",
                                                                    {"method": "password"})


def test_unknown_kind_is_refused(db):
    with pytest.raises(ValueError):
        log_event(db, "n_importe_quoi", now=NOW)


def test_events_are_kept_twelve_months(db):
    log_event(db, "logout", now=NOW - timedelta(days=366))
    log_event(db, "logout", now=NOW - timedelta(days=300))
    assert purge_events(db, NOW) == 1
    assert len(db.scalars(select(SecurityEvent)).all()) == 1


def test_cleanup_job_purges_both_tables(db, make_ctx):
    from app.jobs.cleanup import purge_security_data
    from app.services import ratelimit

    log_event(db, "logout", now=NOW - timedelta(days=400))
    ratelimit.record(db, "login_ip", "203.0.113.5", NOW - timedelta(days=3))
    assert purge_security_data(make_ctx(now=NOW)) == 2
