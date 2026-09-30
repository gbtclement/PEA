from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.jobs.mail import send_pending_emails
from app.models import EmailLog
from app.services.mail.outbox import enqueue
from tests.factories import make_user
from tests.fake_mailer import FakeMailer

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def _enqueue(db, **kw):
    return enqueue(db, "welcome", to="jean@example.com", context={"first_name": "Jean"}, **kw)


def test_enqueue_renders_and_waits(db):
    user = make_user(db, "jean@example.com")
    log_id = _enqueue(db, user_id=user.id)
    row = db.get(EmailLog, log_id)
    assert row.status == "pending" and row.subject == "Bienvenue sur PEA Radar" and "Jean" in row.text


def test_dedupe_key_prevents_duplicates(db):
    assert _enqueue(db, dedupe_key="welcome:1") is not None
    assert _enqueue(db, dedupe_key="welcome:1") is None
    assert len(db.scalars(select(EmailLog)).all()) == 1


def test_worker_sends_pending(db, make_ctx):
    _enqueue(db)
    mailer = FakeMailer()
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW - timedelta(seconds=1)))
    assert send_pending_emails(make_ctx(mailer=mailer, now=NOW)) == 1
    assert mailer.sent[0]["to"] == "jean@example.com"
    row = db.scalars(select(EmailLog)).one()
    assert row.status == "sent" and row.sent_at == NOW and row.attempts == 1
    assert send_pending_emails(make_ctx(mailer=mailer, now=NOW)) == 0  # jamais envoyé deux fois


def test_worker_retries_then_gives_up(db, make_ctx):
    _enqueue(db)
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW))
    mailer = FakeMailer()
    mailer.fail_next = 10
    now = NOW
    for expected_delay in (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30)):
        send_pending_emails(make_ctx(mailer=mailer, now=now))
        row = db.scalars(select(EmailLog)).one()
        assert row.status == "pending" and row.next_attempt_at == now + expected_delay and "SMTP" in row.error
        assert send_pending_emails(make_ctx(mailer=mailer, now=now)) == 0  # pas avant le délai
        now = row.next_attempt_at
    send_pending_emails(make_ctx(mailer=mailer, now=now))
    assert db.scalars(select(EmailLog)).one().status == "failed"
