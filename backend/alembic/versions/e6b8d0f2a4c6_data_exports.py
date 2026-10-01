"""personal data exports

Revision ID: e6b8d0f2a4c6
Revises: d4f6a8c0e2b4
Create Date: 2026-09-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6b8d0f2a4c6"
down_revision: Union[str, Sequence[str], None] = "d4f6a8c0e2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_exports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_exports_user_id", "data_exports", ["user_id"])
    op.create_index("ix_data_exports_expires_at", "data_exports", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_data_exports_expires_at", table_name="data_exports")
    op.drop_index("ix_data_exports_user_id", table_name="data_exports")
    op.drop_table("data_exports")
