import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

PREVIOUS = "75e519660560"
NAME = "pea_radar_migration_test"


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


def test_moi_keeps_data_and_becomes_legacy_admin(migration_url):
    cfg = _config(migration_url)
    command.upgrade(cfg, PREVIOUS)
    engine = create_engine(migration_url)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'Moi')"))
        conn.execute(text("INSERT INTO user_settings (user_id, min_orders_per_year, penalty_fee, fee_grid) "
                          "VALUES (1, 10, 50.0, '[]'::jsonb)"))
        conn.execute(text("INSERT INTO conversations (user_id, title, input_tokens, output_tokens, cost_usd) "
                          "VALUES (1, 'Ma question', 0, 0, 0)"))
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, email, first_name, role, is_premium, email_verified_at FROM users")).one()
        assert user.email == "moi@pea-radar.invalid" and user.first_name == "Moi"
        assert user.role == "admin" and user.is_premium and user.email_verified_at is not None
        assert conn.execute(text("SELECT user_id FROM user_settings")).scalar_one() == user.id
        assert conn.execute(text("SELECT user_id FROM conversations")).scalar_one() == user.id
    columns = {c["name"]: c for c in inspect(engine).get_columns("users")}
    assert str(columns["id"]["type"]) == "UUID" and "name" not in columns
    assert {"sessions", "known_devices", "email_codes", "email_log"} <= set(inspect(engine).get_table_names())
    engine.dispose()
