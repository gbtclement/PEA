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
def fake_captcha():
    from tests.fake_captcha import FakeCaptcha

    return FakeCaptcha()


@pytest.fixture
def fake_breach():
    from tests.fake_breach import FakeBreach

    return FakeBreach()


@pytest.fixture
def fake_google():
    from tests.fake_google import FakeGoogle

    return FakeGoogle()


@pytest.fixture
def fake_billing():
    from tests.fake_billing import FakeBilling

    return FakeBilling()


def _build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing):
    from contextlib import nullcontext

    from app.api.deps import INTRADAY_CACHE, NEWS_CACHE, PLANS_CACHE, get_llm_factory, get_market_provider, get_session_maker

    INTRADAY_CACHE.clear()
    NEWS_CACHE.clear()
    PLANS_CACHE.clear()
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

    from app.api.deps import get_breach_checker, get_captcha, get_google_client

    app.dependency_overrides[get_captcha] = lambda: fake_captcha
    app.dependency_overrides[get_breach_checker] = lambda: fake_breach
    app.dependency_overrides[get_google_client] = lambda: fake_google

    from app.api.deps import get_billing_gateway

    app.dependency_overrides[get_billing_gateway] = lambda: fake_billing
    return app


@pytest.fixture
def user(db):
    from tests.factories import make_user

    return make_user(db, "moi@example.com", first_name="Moi")


@pytest.fixture
def anon_client(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing):
    # https : les cookies « Secure » posés par l'API sont renvoyés comme par un vrai navigateur.
    with TestClient(_build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def client(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing, user):
    """Client connecté avec le compte `user` (validé, rôle utilisateur)."""
    from tests.auth_helpers import sign_in

    with TestClient(_build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing), base_url="https://testserver") as test_client:
        sign_in(test_client, db, user)
        yield test_client


@pytest.fixture
def admin_client(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing):
    """Client connecté avec un compte administrateur."""
    from tests.auth_helpers import sign_in
    from tests.factories import make_user

    with TestClient(_build_app(db, fake_market, fake_llm, fake_captcha, fake_breach, fake_google, fake_billing), base_url="https://testserver") as test_client:
        sign_in(test_client, db, make_user(db, "admin@example.com", first_name="Admin", role="admin"))
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
    def _make(market=None, listing=None, now: datetime | None = None, mailer=None, billing=None, **settings_overrides) -> JobContext:
        return JobContext(
            session_factory=session_factory,
            market=market or FakeMarket(),
            listing=listing or FakeListing(),
            settings=Settings(**settings_overrides),
            now=(lambda: now) if now else (lambda: datetime.now(UTC)),
            mailer=mailer,
            billing=billing,
        )

    return _make


@pytest.fixture
def app_secret(monkeypatch):
    """Clé de signature des liens (désinscription) : vide par défaut en test."""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "app_secret", "secret-de-test")


@pytest.fixture(autouse=True)
def _default_fx_rates():
    """Chaque test part de la table fixe des devises (un test peut charger des cours du jour)."""
    from app.services import fx

    fx.reset()
    yield
    fx.reset()
