from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuthSession, DataExport, EmailCode, EmailLog, User
from app.services.auth.sessions import open_session, resolve_session
from app.services.market_calendar import PARIS
from app.services.privacy.retention import run_retention
from tests.factories import make_security, make_user

NOW = datetime(2029, 12, 1, 3, 30, tzinfo=UTC)


def _age(user, days):
    user.created_at = NOW - timedelta(days=days)
    user.last_login_at = user.last_seen_at = None


def test_unverified_accounts_go_after_7_days(db):
    old = make_user(db, "vieux@example.com", verified=False)
    new = make_user(db, "neuf@example.com", verified=False)
    _age(old, 8)
    _age(new, 2)
    db.flush()
    assert run_retention(db, NOW)["unverified"] == 1
    db.expire_all()
    assert db.get(User, new.id) is not None and db.get(User, old.id) is None


def test_expired_sessions_codes_exports_and_old_mails_go(db):
    user = make_user(db)
    session = open_session(db, user, persistent=False, ip=None, user_agent="x", now=NOW - timedelta(days=2),
                           settings=get_settings()).session
    db.add_all([EmailCode(user_id=user.id, purpose="verify_email", code_hash="h", expires_at=NOW - timedelta(hours=1)),
                DataExport(user_id=user.id, status="ready", content="{}", expires_at=NOW - timedelta(hours=1)),
                EmailLog(kind="welcome", recipient="a@b.c", subject="s", html="h", text="t", status="sent",
                         created_at=NOW - timedelta(days=91)),
                EmailLog(kind="welcome", recipient="a@b.c", subject="s", html="h", text="t", status="sent",
                         created_at=NOW - timedelta(days=10))])
    user.last_login_at = NOW  # compte actif : pas concerné par l'inactivité
    db.flush()
    counts = run_retention(db, NOW)
    assert (counts["sessions"], counts["codes"], counts["exports"], counts["email_log"]) == (1, 1, 1, 1)
    db.expire_all()
    assert db.get(AuthSession, session.id) is None


def test_three_years_without_login_warns_then_deletes_30_days_later(db):
    user = make_user(db, "dormeur@example.com")
    _age(user, 3 * 365 + 1)
    db.flush()
    assert run_retention(db, NOW)["warned"] == 1
    assert user.inactivity_warned_at == NOW
    warning = db.scalars(select(EmailLog).where(EmailLog.kind == "inactivity_warning")).one()
    assert "31/12/2029" in warning.text  # date de suppression annoncée (NOW + 30 jours)
    assert run_retention(db, NOW + timedelta(days=29))["inactive_deleted"] == 0
    assert run_retention(db, NOW + timedelta(days=31))["inactive_deleted"] == 1
    assert db.scalars(select(User).where(User.email == "dormeur@example.com")).first() is None
    assert db.scalars(select(EmailLog).where(EmailLog.kind == "account_deleted")).one()


def test_inactivity_never_deletes_admins_or_accounts_back_in_use(db):
    admin = make_user(db, "admin@example.com", role="admin")
    back = make_user(db, "revenu@example.com")
    _age(admin, 4 * 365)
    _age(back, 4 * 365)
    db.flush()
    counts = run_retention(db, NOW)
    assert counts["warned"] == 1 and admin.inactivity_warned_at is None
    back.last_login_at = NOW + timedelta(days=5)  # reconnecté après le C8
    db.flush()
    assert run_retention(db, NOW + timedelta(days=40))["inactive_deleted"] == 0
    db.expire_all()
    assert db.get(User, back.id) is not None and db.get(User, back.id).inactivity_warned_at is None


def test_using_a_remembered_session_counts_as_activity(db):
    user = make_user(db)
    new = open_session(db, user, persistent=True, ip=None, user_agent="x", now=NOW - timedelta(days=1),
                       settings=get_settings())
    resolve_session(db, new.token, now=NOW, settings=get_settings())
    db.expire_all()
    assert db.get(User, user.id).last_seen_at == NOW


def test_old_score_snapshots_and_move_notices_are_purged(db, user):
    from app.models import MoveNotice, ScoreSnapshot

    security = make_security(db, "MC.PA")
    today = NOW.astimezone(PARIS).date()
    db.add_all([
        ScoreSnapshot(day=today - timedelta(days=15), security_id=security.id, total=50),
        ScoreSnapshot(day=today - timedelta(days=13), security_id=security.id, total=50),
        MoveNotice(user_id=user.id, security_id=security.id, day=today - timedelta(days=8)),
        MoveNotice(user_id=user.id, security_id=security.id, day=today - timedelta(days=6)),
    ])
    db.flush()
    counts = run_retention(db, NOW)
    assert (counts["score_snapshots"], counts["move_notices"]) == (1, 1)
