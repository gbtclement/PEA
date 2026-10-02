import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "c5e7a9b1d3f5"
NAME = "pea_radar_migration_history_test"


@pytest.fixture
def migration_url():
    base = make_url(get_settings().test_database_url)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {NAME}"))
    yield base.set(database=NAME).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {NAME} WITH (FORCE)"))
    admin.dispose()


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    return cfg


def test_existing_securities_start_with_incomplete_history(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO securities (id, yahoo_ticker, symbol, name, kind, market, active, created_at, updated_at) "
                          "VALUES (1, 'MC.PA', 'MC', 'LVMH', 'stock', 'Euronext Paris', true, now(), now())"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT history_complete FROM securities WHERE id = 1")).scalar() is False
    command.downgrade(cfg, PREVIOUS)
    engine.dispose()
