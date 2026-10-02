from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.base import ListingProvider, MarketDataProvider
from app.services.mail.smtp import Mailer

if TYPE_CHECKING:
    from app.services.billing.gateway import BillingGateway


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class JobContext:
    session_factory: Callable[[], AbstractContextManager[Session]]
    market: MarketDataProvider
    listings: Sequence[ListingProvider]
    settings: Settings
    now: Callable[[], datetime] = utcnow
    mailer: Mailer | None = None
    billing: "BillingGateway | None" = None
