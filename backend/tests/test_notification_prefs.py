import uuid

from app.models import NotificationPrefs
from app.services.notifications.prefs import get_prefs, recipients, save_prefs
from app.services.notifications.unsubscribe import make_token, read_token
from tests.factories import make_user


def test_defaults_without_a_row(db, user):
    prefs = get_prefs(db, user.id)
    assert (prefs.price_move, prefs.price_alert, prefs.daily_recap, prefs.weekly_recap, prefs.order_reminder,
            prefs.score_change) == (True, True, False, False, True, False)
    assert prefs.move_threshold_pct == 5.0
    assert db.get(NotificationPrefs, user.id) is None  # rien n'est écrit tant que le membre n'a rien réglé


def test_save_creates_then_updates_the_row(db, user):
    save_prefs(db, user.id, {"daily_recap": True, "move_threshold_pct": 3.0})
    save_prefs(db, user.id, {"price_move": False})
    row = db.get(NotificationPrefs, user.id)
    assert (row.daily_recap, row.price_move, row.move_threshold_pct) == (True, False, 3.0)


def test_recipients_follow_prefs_and_skip_unverified(db, user):
    other = make_user(db, "autre@example.com")
    make_user(db, "pasvalide@example.com", verified=False)
    save_prefs(db, other.id, {"price_move": False, "daily_recap": True})
    assert [u.email for u, _ in recipients(db, "price_move")] == ["moi@example.com"]
    assert [u.email for u, _ in recipients(db, "daily_recap")] == ["autre@example.com"]


def test_unsubscribe_token_round_trip():
    user_id = uuid.uuid4()
    token = make_token(user_id, "s3cret")
    assert read_token(token, "s3cret") == user_id
    assert read_token(token, "autre-secret") is None
    assert read_token(token[:-1] + ("A" if token[-1] != "A" else "B"), "s3cret") is None
    assert read_token(make_token(uuid.uuid4(), "s3cret").split(".")[0] + "." + token.split(".")[1], "s3cret") is None
    assert read_token("n'importe quoi", "s3cret") is None
    assert read_token(token, "") is None
    assert read_token(None, "s3cret") is None
