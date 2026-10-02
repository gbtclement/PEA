"""universe: securities.currency, securities.source and the fx_rates table

Revision ID: e3b5d7f9a1c3
Revises: d7f9b1c3e5a7
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e3b5d7f9a1c3"
down_revision: Union[str, Sequence[str], None] = "d7f9b1c3e5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("securities", sa.Column("currency", sa.String(8), nullable=True))
    op.add_column("securities", sa.Column("source", sa.String(16), nullable=True))
    # Titres existants : actions de la liste Euronext, le reste vient des listes saisies à la main (seeds/).
    op.execute("UPDATE securities SET source = CASE WHEN kind = 'stock' AND (market LIKE 'Euronext%' OR market LIKE 'Oslo%') "
               "THEN 'euronext' ELSE 'seed' END")
    op.create_table(
        "fx_rates",
        sa.Column("currency", sa.String(8), primary_key=True),
        sa.Column("rate_to_eur", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fx_rates")
    op.drop_column("securities", "source")
    op.drop_column("securities", "currency")
