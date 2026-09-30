from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuthSession
from app.services.auth.sessions import open_session
from tests.factories import make_user


def other_session(db, user, *, agent="Mozilla/5.0 (Windows NT 10.0) Firefox/130.0", days_ago=0):
    now = datetime.now(UTC) - timedelta(days=days_ago)
    return open_session(db, user, persistent=True, ip="198.51.100.20", user_agent=agent, now=now,
                        settings=get_settings()).session


def test_lists_my_sessions_with_the_current_one_flagged(client, db, user):
    other = other_session(db, user)
    make_user(db, "x@example.com")
    rows = client.get("/api/me/sessions").json()
    assert len(rows) == 2
    current = [r for r in rows if r["current"]]
    assert len(current) == 1 and current[0]["id"] != str(other.id)
    assert next(r for r in rows if r["id"] == str(other.id))["ip"] == "198.51.100.0/24"
    assert "token_hash" not in client.get("/api/me/sessions").text and "csrf" not in client.get("/api/me/sessions").text


def test_expired_sessions_are_hidden(client, db, user):
    other = other_session(db, user)
    other.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert len(client.get("/api/me/sessions").json()) == 1


def test_revoke_one_session(client, db, user):
    other = other_session(db, user)
    assert client.delete(f"/api/me/sessions/{other.id}").status_code == 204
    assert db.get(AuthSession, other.id) is None


def test_cannot_revoke_someone_elses_session(client, db):
    stranger = other_session(db, make_user(db, "x@example.com"))
    assert client.delete(f"/api/me/sessions/{stranger.id}").status_code == 404
    assert db.get(AuthSession, stranger.id) is not None


def test_revoke_all_others_keeps_this_one(client, db, user):
    other_session(db, user)
    other_session(db, user)
    assert client.delete("/api/me/sessions").status_code == 204
    remaining = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all()
    assert len(remaining) == 1
    assert client.get("/api/me").status_code == 200  # toujours connecté ici


def test_revoking_the_current_session_signs_out(client, db, user):
    current = client.get("/api/me/sessions").json()[0]
    assert client.delete(f"/api/me/sessions/{current['id']}").status_code == 204
    assert client.get("/api/me").status_code == 401
