"""data exports: failed status, one pending export per user

Revision ID: a2b4c6d8e0f2
Revises: f1a3c5e7b9d1
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b4c6d8e0f2"
down_revision: Union[str, Sequence[str], None] = "f1a3c5e7b9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("uq_data_exports_one_pending", "data_exports", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index("uq_data_exports_one_pending", table_name="data_exports")
