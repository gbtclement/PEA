"""app settings, monthly AI usage, no more Claude key in the database

Revision ID: d4f6a8c0e2b4
Revises: c1e7a9d3f5b2
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6a8c0e2b4"
down_revision: Union[str, Sequence[str], None] = "c1e7a9d3f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ai_model", sa.String(64), nullable=False, server_default="claude-opus-5"),
        sa.Column("ai_monthly_cost_limit_usd", sa.Float(), nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="app_settings_single_row"),
    )
    # Le modèle choisi par « Moi » devient le modèle par défaut de tout le monde.
    op.execute("INSERT INTO app_settings (id, ai_model) SELECT 1, COALESCE("
               "(SELECT ai_model FROM user_settings WHERE ai_model IS NOT NULL LIMIT 1), 'claude-opus-5')")
    op.create_table(
        "ai_usage",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("month", sa.String(7), primary_key=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
    )
    # Reprise des coûts déjà dépensés, pour que la limite du mois en cours en tienne compte.
    op.execute(
        "INSERT INTO ai_usage (user_id, month, cost_usd) "
        "SELECT c.user_id, to_char(m.created_at AT TIME ZONE 'Europe/Paris', 'YYYY-MM'), SUM(m.cost_usd) "
        "FROM messages m JOIN conversations c ON c.id = m.conversation_id GROUP BY 1, 2"
    )
    # La clé Claude n'est plus lue qu'à partir de ANTHROPIC_API_KEY (.env).
    op.drop_column("user_settings", "anthropic_key_enc")
    op.drop_column("user_settings", "ai_model")


def downgrade() -> None:
    op.add_column("user_settings", sa.Column("ai_model", sa.String(64), nullable=True))
    op.add_column("user_settings", sa.Column("anthropic_key_enc", sa.Text(), nullable=True))
    op.drop_table("ai_usage")
    op.drop_table("app_settings")
