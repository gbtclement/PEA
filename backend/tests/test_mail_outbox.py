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


def test_codes_and_links_are_erased_once_sent_or_abandoned(db, make_ctx):
    user = make_user(db, "jean@example.com")
    enqueue(db, "verify_code", to=user.email, user_id=user.id, context={"first_name": "Jean", "code": "482913"})
    enqueue(db, "reset_password", to=user.email, user_id=user.id,
            context={"first_name": "Jean", "token": "jeton-secret-reset", "valid_minutes": 30})
    _enqueue(db)
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW))
    mailer = FakeMailer()
    send_pending_emails(make_ctx(mailer=mailer, now=NOW))
    assert "482913" in mailer.sent[0]["subject"] and "jeton-secret-reset" in mailer.sent[1]["text"]  # envoyés intacts
    rows = {row.kind: row for row in db.scalars(select(EmailLog))}
    for kind, secret in (("verify_code", "482913"), ("reset_password", "jeton-secret-reset")):
        row = rows[kind]
        assert row.status == "sent" and secret not in row.subject + row.html + row.text
    assert rows["verify_code"].subject == "Votre code PEA Radar"
    assert "Jean" in rows["welcome"].text  # rien de secret : gardé tel quel


def test_an_abandoned_code_is_erased_too(db, make_ctx):
    enqueue(db, "verify_code", to="jean@example.com", context={"first_name": "Jean", "code": "482913"})
    db.execute(EmailLog.__table__.update().values(next_attempt_at=NOW, attempts=3))
    mailer = FakeMailer()
    mailer.fail_next = 1
    send_pending_emails(make_ctx(mailer=mailer, now=NOW))
    row = db.scalars(select(EmailLog)).one()
    assert row.status == "failed" and "482913" not in row.subject + row.html + row.text
