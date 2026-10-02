import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "d7f9b1c3e5a7"
NAME = "pea_radar_migration_sources_test"


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


def test_existing_securities_get_their_source(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    columns = "(id, yahoo_ticker, symbol, name, kind, market, active, history_complete, created_at, updated_at)"
    with engine.begin() as conn:
        for row in ("1, 'MC.PA', 'MC', 'LVMH', 'stock', 'Euronext Paris'", "2, 'SAP.DE', 'SAP', 'SAP', 'stock', 'Xetra'",
                    "3, 'CW8.PA', 'CW8', 'Amundi World', 'etf', 'Euronext Paris'", "4, '2020.OL', '2020', 'Bulkers', 'stock', 'Oslo Børs'"):
            conn.execute(text(f"INSERT INTO securities {columns} VALUES ({row}, true, false, now(), now())"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, source, currency FROM securities ORDER BY id")).all()
        assert [tuple(r) for r in rows] == [(1, "euronext", None), (2, "seed", None), (3, "seed", None), (4, "euronext", None)]
        assert conn.execute(text("SELECT count(*) FROM fx_rates")).scalar() == 0
    command.downgrade(cfg, PREVIOUS)
    engine.dispose()
