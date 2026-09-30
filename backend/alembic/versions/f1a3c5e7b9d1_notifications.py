"""notification preferences, price alerts, score snapshots

Revision ID: f1a3c5e7b9d1
Revises: e6b8d0f2a4c6
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a3c5e7b9d1"
down_revision: Union[str, Sequence[str], None] = "e6b8d0f2a4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_prefs",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("price_move", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("price_alert", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("daily_recap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("weekly_recap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("order_reminder", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("score_change", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("move_threshold_pct", sa.Float(), nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_price_alerts_user_id", "price_alerts", ["user_id"])
    op.create_index("ix_price_alerts_active", "price_alerts", ["active", "security_id"])
    op.create_table(
        "score_snapshots",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total", sa.Float(), nullable=False),
        sa.Column("top_rank", sa.Integer(), nullable=True),
    )
    op.create_table(
        "move_notices",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("move_notices")
    op.drop_table("score_snapshots")
    op.drop_index("ix_price_alerts_active", table_name="price_alerts")
    op.drop_index("ix_price_alerts_user_id", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_table("notification_prefs")
