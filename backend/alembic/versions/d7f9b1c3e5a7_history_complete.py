"""history: securities.history_complete for the full-history backfill

Revision ID: d7f9b1c3e5a7
Revises: c5e7a9b1d3f5
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7f9b1c3e5a7"
down_revision: Union[str, Sequence[str], None] = "c5e7a9b1d3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Faux pour les titres existants : le rattrapage charge leurs cours antérieurs aux 5 ans déjà stockés.
    op.add_column("securities", sa.Column("history_complete", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("securities", "history_complete")
