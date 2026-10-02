"""securities.fundamentals_checked_at for the weekly fundamentals rotation

Revision ID: f5c7e9a1b3d5
Revises: e3b5d7f9a1c3
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5c7e9a1b3d5"
down_revision: Union[str, Sequence[str], None] = "e3b5d7f9a1c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vide pour les titres existants : la première semaine relit tout le monde, dans l'ordre des identifiants.
    op.add_column("securities", sa.Column("fundamentals_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("securities", "fundamentals_checked_at")
