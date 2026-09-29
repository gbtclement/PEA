from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.yahoo import YahooProvider
from app.services.cache import TTLCache

INTRADAY_CACHE = TTLCache(60)
NEWS_CACHE = TTLCache(900)


@lru_cache
def get_market_provider() -> MarketDataProvider:
    """Seul accès de l'API à Yahoo : intraday et actualités, à la demande et mis en cache."""
    settings = get_settings()
    return YahooProvider(chunk_size=settings.yahoo_chunk_size, pause_seconds=settings.yahoo_pause_seconds)


def get_llm_factory():
    """Fabrique le client Claude pour une clé donnée ; remplacée par un faux client en test."""
    import anthropic

    def make(api_key: str):
        return anthropic.Anthropic(api_key=api_key, max_retries=2).beta.messages

    return make


def get_session_maker():
    """Ouvre des sessions hors requête (fil de réponse de l'assistant) ; remplacée en test."""
    from app.core.db import get_session_factory

    return get_session_factory()


def get_captcha():
    """Turnstile si la clé secrète est configurée, sinon captcha désactivé ; remplacé en test."""
    from app.services.auth.captcha import DisabledCaptcha, TurnstileVerifier

    secret = get_settings().turnstile_secret_key
    return TurnstileVerifier(secret) if secret else DisabledCaptcha()


def get_breach_checker():
    """Have I Been Pwned (désactivable par HIBP_ENABLED=false) ; remplacé en test."""
    from app.services.auth.breach import HibpChecker, NoBreachCheck

    return HibpChecker() if get_settings().hibp_enabled else NoBreachCheck()


def get_google_client():
    """Client Google, ou None si GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET ou APP_SECRET manque ; remplacé en test."""
    from app.services.auth.google import GoogleOIDC

    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret and settings.app_secret):
        return None
    return GoogleOIDC(settings.google_client_id, settings.google_client_secret)
