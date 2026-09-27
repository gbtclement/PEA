import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(get_settings().test_database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def fake_market():
    from tests.fakes import FakeMarket

    return FakeMarket()


@pytest.fixture
def fake_llm():
    from tests.fake_llm import FakeLLM

    return FakeLLM()


@pytest.fixture
def client(db, fake_market, fake_llm):
    from contextlib import nullcontext

    from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, get_llm_factory, get_market_provider, get_session_maker

    INTRADAY_CACHE.clear()
    NEWS_CACHE.clear()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_market_provider] = lambda: fake_market

    def llm_factory():
        def make(api_key: str):
            fake_llm.api_keys.append(api_key)
            return fake_llm
        return make

    app.dependency_overrides[get_llm_factory] = llm_factory
    app.dependency_overrides[get_session_maker] = lambda: (lambda: nullcontext(db))
    with TestClient(app) as test_client:
        yield test_client


from contextlib import contextmanager
from datetime import UTC, datetime

from app.core.config import Settings
from app.jobs.context import JobContext
from tests.fakes import FakeListing, FakeMarket


@pytest.fixture
def session_factory(db):
    @contextmanager
    def factory():
        yield db

    return factory


@pytest.fixture
def make_ctx(session_factory):
    def _make(market=None, listing=None, now: datetime | None = None, **settings_overrides) -> JobContext:
        return JobContext(
            session_factory=session_factory,
            market=market or FakeMarket(),
            listing=listing or FakeListing(),
            settings=Settings(**settings_overrides),
            now=(lambda: now) if now else (lambda: datetime.now(UTC)),
        )

    return _make
