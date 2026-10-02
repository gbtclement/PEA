import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "b3c5d7e9f1a3"
NAME = "pea_radar_migration_envelopes_test"


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


def test_eligibility_columns_become_pea_rows(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        insert = ("INSERT INTO securities (id, yahoo_ticker, symbol, name, kind, market, eligibility, eligibility_source, "
                  "eligibility_override, active, created_at, updated_at) VALUES "
                  "(:id, :t, :t, :t, :kind, 'Euronext Paris', :e, :s, :o, true, now(), now())")
        conn.execute(text(insert), [
            {"id": 1, "t": "MC.PA", "kind": "stock", "e": "eligible", "s": "auto", "o": None},
            {"id": 2, "t": "GFC.PA", "kind": "stock", "e": "eligible", "s": "override", "o": "eligible"},
            {"id": 3, "t": "CW8.PA", "kind": "etf", "e": "eligible", "s": "seed", "o": None},
            {"id": 4, "t": "MMM.PA", "kind": "stock", "e": "non_eligible", "s": "auto", "o": None},
        ])
        conn.execute(text("INSERT INTO score_snapshots (day, security_id, total, top_rank) VALUES "
                          "('2026-10-01', 1, 80, 1), ('2026-10-01', 4, 50, NULL)"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT security_id, envelope, status, source, override FROM security_envelopes "
                                 "ORDER BY security_id")).all()
        assert [tuple(r) for r in rows] == [
            (1, "pea", "eligible", "auto", None),
            (2, "pea", "eligible", "manual", "eligible"),
            (3, "pea", "eligible", "seed", None),
            (4, "pea", "non_eligible", "auto", None),
        ]
        pool = dict(conn.execute(text("SELECT security_id, top_pool FROM score_snapshots")).all())  # inconnu avant les enveloppes
        assert pool == {1: None, 4: None}
    inspector = inspect(engine)
    assert not {"eligibility", "eligibility_source", "eligibility_override"} & {c["name"] for c in inspector.get_columns("securities")}
    assert {"employees", "revenue", "revenue_currency"} <= {c["name"] for c in inspector.get_columns("fundamentals")}
    assert "envelopes" in {c["name"] for c in inspector.get_columns("user_settings")}
    command.downgrade(cfg, PREVIOUS)
    with engine.connect() as conn:
        back = conn.execute(text("SELECT eligibility, eligibility_source, eligibility_override FROM securities WHERE id = 2")).one()
        assert tuple(back) == ("eligible", "override", "eligible")
    engine.dispose()
