"""billing: subscriptions, stripe events, billing consents, stripe cancellations

Revision ID: b3c5d7e9f1a3
Revises: a2b4c6d8e0f2
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c5d7e9f1a3"
down_revision: Union[str, Sequence[str], None] = "a2b4c6d8e0f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("interval", sa.String(5)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("renewal_notice_sent_for", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stripe_events_received_at", "stripe_events", ["received_at"])
    op.create_table(
        "billing_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cgv_version", sa.String(20), nullable=False),
        sa.Column("withdrawal_waiver", sa.Boolean(), nullable=False),
        sa.Column("interval", sa.String(5), nullable=False),
        sa.Column("checkout_session_id", sa.String(255)),
        sa.Column("ip", sa.String(64)),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_billing_consents_user_id", "billing_consents", ["user_id"])
    op.create_table(
        "stripe_cancellations",
        sa.Column("subscription_id", sa.String(255), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("stripe_cancellations")
    op.drop_index("ix_billing_consents_user_id", table_name="billing_consents")
    op.drop_table("billing_consents")
    op.drop_index("ix_stripe_events_received_at", table_name="stripe_events")
    op.drop_table("stripe_events")
    op.drop_table("subscriptions")
