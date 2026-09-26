from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.base import ListingProvider, MarketDataProvider


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class JobContext:
    session_factory: Callable[[], AbstractContextManager[Session]]
    market: MarketDataProvider
    listing: ListingProvider
    settings: Settings
    now: Callable[[], datetime] = utcnow
