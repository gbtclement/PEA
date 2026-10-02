"""envelopes: security_envelopes, user envelopes, fundamentals size, snapshot top pool

Revision ID: c5e7a9b1d3f5
Revises: b3c5d7e9f1a3
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e7a9b1d3f5"
down_revision: Union[str, Sequence[str], None] = "b3c5d7e9f1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_envelopes",
        sa.Column("security_id", sa.Integer(), sa.ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("envelope", sa.String(16), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("override", sa.String(16), nullable=True),
    )
    op.create_index("ix_security_envelopes_envelope_status", "security_envelopes", ["envelope", "status"])
    # L'ancienne éligibilité est celle du PEA ; « override » devient « manual ». Le PEA-PME est calculé par le worker.
    op.execute("""
        INSERT INTO security_envelopes (security_id, envelope, status, source, override)
        SELECT id, 'pea', eligibility,
               CASE eligibility_source WHEN 'override' THEN 'manual' ELSE eligibility_source END,
               eligibility_override
        FROM securities
    """)
    op.drop_index("ix_securities_eligibility", table_name="securities")
    op.drop_column("securities", "eligibility_override")
    op.drop_column("securities", "eligibility_source")
    op.drop_column("securities", "eligibility")
    op.add_column("fundamentals", sa.Column("employees", sa.Integer(), nullable=True))
    op.add_column("fundamentals", sa.Column("revenue", sa.Float(), nullable=True))
    op.add_column("fundamentals", sa.Column("revenue_currency", sa.String(3), nullable=True))
    op.add_column("user_settings", sa.Column("envelopes", postgresql.JSONB(), nullable=False,
                                             server_default=sa.text("'[]'::jsonb")))
    op.add_column("score_snapshots", sa.Column("top_pool", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE score_snapshots SET top_pool = (top_rank IS NOT NULL)")


def downgrade() -> None:
    op.drop_column("score_snapshots", "top_pool")
    op.drop_column("user_settings", "envelopes")
    op.drop_column("fundamentals", "revenue_currency")
    op.drop_column("fundamentals", "revenue")
    op.drop_column("fundamentals", "employees")
    op.add_column("securities", sa.Column("eligibility", sa.String(16), nullable=False, server_default="a_verifier"))
    op.add_column("securities", sa.Column("eligibility_source", sa.String(16), nullable=False, server_default="auto"))
    op.add_column("securities", sa.Column("eligibility_override", sa.String(16), nullable=True))
    op.create_index("ix_securities_eligibility", "securities", ["eligibility"])
    op.execute("""
        UPDATE securities s SET eligibility = e.status,
               eligibility_source = CASE e.source WHEN 'manual' THEN 'override' ELSE e.source END,
               eligibility_override = CASE WHEN e.override IN ('eligible', 'non_eligible') THEN e.override END
        FROM security_envelopes e WHERE e.security_id = s.id AND e.envelope = 'pea'
    """)
    op.drop_table("security_envelopes")
