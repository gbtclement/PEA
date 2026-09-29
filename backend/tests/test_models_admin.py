from sqlalchemy import inspect

from app.models import AppSettings, UserSettings
from app.repositories.app_settings import get_app_settings
from app.schemas.auth import MeOut
from tests.factories import make_user


def test_app_settings_single_row_with_defaults(db):
    first = get_app_settings(db)
    assert (first.id, first.ai_model, first.ai_monthly_cost_limit_usd) == (1, "claude-opus-5", 5.0)
    assert get_app_settings(db) is first
    assert db.query(AppSettings).count() == 1


def test_user_settings_no_longer_hold_a_key():
    columns = {c.key for c in inspect(UserSettings).columns}
    assert "anthropic_key_enc" not in columns and "ai_model" not in columns


def test_me_exposes_sign_in_methods_and_premium(db):
    google_only = make_user(db, "g@example.com", password=None)
    google_only.google_sub = "sub-1"
    admin = make_user(db, "a@example.com", role="admin")
    out = MeOut.model_validate(google_only)
    assert (out.has_password, out.has_google, out.has_premium) == (False, True, False)
    assert MeOut.model_validate(admin).has_premium is True  # un admin est toujours Premium
