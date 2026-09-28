"""user accounts: UUID users, sessions, e-mail codes, e-mail outbox

Revision ID: a7c3e9f1b2d4
Revises: 75e519660560
Create Date: 2026-09-28

Migration à sens unique : les identifiants entiers des utilisateurs deviennent des UUID.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c3e9f1b2d4"
down_revision: Union[str, Sequence[str], None] = "75e519660560"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHILDREN = ("orders", "favorites", "conversations", "user_settings")
LEGACY_EMAIL = "moi@pea-radar.invalid"


def upgrade() -> None:
    # 1. Un UUID pour chaque utilisateur, recopié dans les tables qui pointent vers lui.
    op.execute("ALTER TABLE users ADD COLUMN uuid uuid NOT NULL DEFAULT gen_random_uuid()")
    for table in CHILDREN:
        op.execute(f"ALTER TABLE {table} ADD COLUMN user_uuid uuid")
        op.execute(f"UPDATE {table} t SET user_uuid = u.uuid FROM users u WHERE u.id = t.user_id")
        # Supprimer la colonne emporte sa clé étrangère, ses index et la clé primaire qui l'utilise.
        op.execute(f"ALTER TABLE {table} DROP COLUMN user_id")
        op.execute(f"ALTER TABLE {table} RENAME COLUMN user_uuid TO user_id")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL")

    # 2. Identité : prénom, nom, adresse. Le premier utilisateur est « Moi », repris par ADMIN_EMAIL.
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))
    op.execute(
        "UPDATE users SET first_name = name, last_name = '', email = CASE "
        f"WHEN id = (SELECT min(id) FROM users) THEN '{LEGACY_EMAIL}' "
        "ELSE 'utilisateur-' || id || '@pea-radar.invalid' END"
    )
    op.execute("ALTER TABLE users DROP COLUMN id")
    op.execute("ALTER TABLE users DROP COLUMN name")
    op.execute("ALTER TABLE users RENAME COLUMN uuid TO id")
    op.execute("ALTER TABLE users ALTER COLUMN id DROP DEFAULT")
    op.create_primary_key("users_pkey", "users", ["id"])
    for column in ("email", "first_name", "last_name"):
        op.alter_column("users", column, nullable=False)
    op.create_unique_constraint("users_email_key", "users", ["email"])
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_unique_constraint("users_google_sub_key", "users", ["google_sub"])
    op.add_column("users", sa.Column("role", sa.String(10), nullable=False, server_default="user"))
    op.add_column("users", sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()))
    for column in ("email_verified_at", "terms_accepted_at", "locked_until", "inactivity_warned_at",
                   "last_login_at", "last_seen_at"):
        op.add_column("users", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
    op.execute(f"UPDATE users SET role = 'admin', is_premium = true, email_verified_at = now() WHERE email = '{LEGACY_EMAIL}'")

    # 3. Clés des tables enfants, recréées sur les UUID.
    for table in CHILDREN:
        op.create_foreign_key(f"{table}_user_id_fkey", table, "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_primary_key("favorites_pkey", "favorites", ["user_id", "security_id"])
    op.create_primary_key("user_settings_pkey", "user_settings", ["user_id"])
    op.create_index("ix_orders_user_date", "orders", ["user_id", "trade_date"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # 4. Nouvelles tables.
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("device", sa.String(100), nullable=False),
        sa.Column("ip", sa.String(50), nullable=True),
        sa.Column("persistent", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table(
        "known_devices",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "email_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("new_email", sa.String(254), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_codes_user_id", "email_codes", ["user_id"])
    op.create_index("ix_email_codes_code_hash", "email_codes", ["code_hash"])
    op.create_table(
        "email_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("headers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("dedupe_key", sa.String(120), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_email_log_user_id", "email_log", ["user_id"])
    op.create_index("ix_email_log_pending", "email_log", ["status", "next_attempt_at"])


def downgrade() -> None:
    raise NotImplementedError("Migration à sens unique : restaurer une sauvegarde de la base pour revenir en arrière.")
