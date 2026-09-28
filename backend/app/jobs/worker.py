import logging

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.jobs.context import JobContext
from app.jobs.scheduler import build_scheduler
from app.providers.euronext import EuronextListingProvider
from app.providers.yahoo import YahooProvider
from app.services.mail.smtp import mailer_from_settings


def build_context() -> JobContext:
    settings = get_settings()
    return JobContext(
        session_factory=get_session_factory(),
        market=YahooProvider(
            chunk_size=settings.yahoo_chunk_size,
            pause_seconds=settings.yahoo_pause_seconds,
            fundamentals_pause_seconds=settings.fundamentals_pause_seconds,
        ),
        listing=EuronextListingProvider(settings.euronext_list_url),
        settings=settings,
        mailer=mailer_from_settings(settings),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    build_scheduler(build_context()).start()


if __name__ == "__main__":
    main()
