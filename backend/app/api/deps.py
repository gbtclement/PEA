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
