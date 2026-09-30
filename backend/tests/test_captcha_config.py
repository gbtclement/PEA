from app.api.deps import get_captcha
from app.core.config import get_settings
from app.services.auth.captcha import DisabledCaptcha, TurnstileVerifier


def test_turnstile_needs_both_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "turnstile_secret_key", "secret")
    monkeypatch.setattr(settings, "turnstile_site_key", "")
    assert isinstance(get_captcha(), DisabledCaptcha)  # sans widget, exiger un jeton bloquerait la connexion
    monkeypatch.setattr(settings, "turnstile_site_key", "site")
    assert isinstance(get_captcha(), TurnstileVerifier)
