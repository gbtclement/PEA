import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.jobs.privacy import build_pending_exports
from app.models import ChatMessage, Conversation, DataExport, EmailLog, Order
from tests.auth_helpers import sign_in
from tests.factories import make_security, make_user


def _ready(client, make_ctx) -> str:
    created = client.post("/api/me/export")
    assert created.status_code == 202 and created.json()["status"] == "pending"
    assert build_pending_exports(make_ctx()) == 1
    return created.json()["id"]


def test_export_contains_the_personal_data_and_mails_a_link(client, db, user, make_ctx):
    security = make_security(db, "AIR.PA")
    db.add(Order(user_id=user.id, security_id=security.id, side="buy", quantity=2, unit_price=10.0, fee=1.0,
                 trade_date=date(2026, 9, 1)))
    conv = Conversation(user_id=user.id, title="Q")
    db.add(conv)
    db.flush()
    db.add(ChatMessage(conversation_id=conv.id, role="user", content="Bonjour"))
    db.flush()
    export_id = _ready(client, make_ctx)
    download = client.get(f"/api/me/export/{export_id}")
    assert download.status_code == 200
    assert "attachment" in download.headers["content-disposition"]
    data = json.loads(download.content)
    assert data["profil"]["email"] == "moi@example.com" and "password_hash" not in data["profil"]
    assert data["ordres"][0]["quantity"] == 2 and data["ordres"][0]["titre"]["symbol"] == "AIR"
    assert data["conversations"][0]["messages"][0]["content"] == "Bonjour"
    for key in ("reglages", "favoris", "usage_assistant", "appareils"):
        assert key in data
    assert all("token_hash" not in s and "csrf_token" not in s for s in data["appareils"])
    mail = db.scalars(select(EmailLog).where(EmailLog.kind == "data_export_ready")).one()
    assert "/reglages" in mail.text


def test_one_export_at_a_time_and_one_per_day(client, make_ctx):
    client.post("/api/me/export")
    again = client.post("/api/me/export")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "export_pending"
    build_pending_exports(make_ctx())
    same_day = client.post("/api/me/export")
    assert same_day.status_code == 429 and same_day.json()["detail"]["code"] == "export_limit"
    latest = client.get("/api/me/export").json()
    assert latest["status"] == "ready" and latest["expires_at"] is not None


def test_export_download_is_owner_only_and_expires(client, anon_client, db, make_ctx):
    export_id = _ready(client, make_ctx)
    sign_in(anon_client, db, make_user(db, "autre@example.com"))
    assert anon_client.get(f"/api/me/export/{export_id}").status_code == 404
    row = db.get(DataExport, export_id)
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert client.get(f"/api/me/export/{export_id}").status_code == 404


def test_pending_export_cannot_be_downloaded(client):
    export_id = client.post("/api/me/export").json()["id"]
    assert client.get(f"/api/me/export/{export_id}").status_code == 404


def test_latest_export_is_null_at_first(client):
    assert client.get("/api/me/export").json() is None
