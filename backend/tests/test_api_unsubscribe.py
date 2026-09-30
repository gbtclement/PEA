import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models import SecurityEvent
from app.services.notifications.prefs import KINDS, get_prefs
from app.services.notifications.unsubscribe import make_token
from tests.factories import make_user

pytestmark = pytest.mark.usefixtures("app_secret")


def _token(user):
    return make_token(user.id, get_settings().app_secret)


def test_check_link(anon_client, user):
    response = anon_client.get(f"/api/unsubscribe?jeton={_token(user)}&type=daily_recap")
    assert response.json() == {"kind": "daily_recap", "label": "Récap du soir"}
    assert anon_client.get(f"/api/unsubscribe?jeton={_token(user)}").json() == {"kind": None, "label": None}


def test_one_click_disables_one_notification(anon_client, db, user):
    # Ce que font Gmail ou Outlook : un POST sans cookie ni en-tête Origin (RFC 8058).
    response = anon_client.post(f"/api/unsubscribe?jeton={_token(user)}&type=price_move",
                                content="List-Unsubscribe=One-Click",
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 200
    db.expire_all()
    prefs = get_prefs(db, user.id)
    assert prefs.price_move is False and prefs.price_alert is True
    event = db.scalar(select(SecurityEvent).where(SecurityEvent.kind == "unsubscribed"))
    assert event.user_id == user.id and event.details == {"kind": "price_move"}


def test_without_type_disables_everything(anon_client, db, user):
    assert anon_client.post(f"/api/unsubscribe?jeton={_token(user)}").status_code == 200
    db.expire_all()
    prefs = get_prefs(db, user.id)
    assert not any(getattr(prefs, kind) for kind in KINDS)


def test_forged_or_unknown_links_are_404(anon_client, db, user):
    other = make_user(db, "autre@example.com")
    forged = _token(other).split(".")[0] + "." + _token(user).split(".")[1]  # identifiant d'un autre, signature du mien
    for query in (f"jeton={forged}", "jeton=abc", f"jeton={_token(user)}&type=inconnu"):
        assert anon_client.get(f"/api/unsubscribe?{query}").status_code == 404
        response = anon_client.post(f"/api/unsubscribe?{query}")
        assert response.status_code == 404 and response.json()["detail"]["code"] == "bad_link"
    db.expire_all()
    assert get_prefs(db, other.id).price_move is True
