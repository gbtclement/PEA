"""erase codes and links from mails already sent

Revision ID: c1e7a9d3f5b2
Revises: b8d4f0a2c3e5
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1e7a9d3f5b2"
down_revision: Union[str, Sequence[str], None] = "b8d4f0a2c3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ERASED = "Contenu effacé après l'envoi : ce mail contenait un code ou un lien personnel."


def upgrade() -> None:
    # Même effacement que le worker (app.services.mail.outbox.forget_secrets), pour les mails partis avant lui.
    op.execute(sa.text(
        "UPDATE email_log SET html = :erased, text = :erased, "
        "subject = CASE WHEN kind = 'verify_code' THEN 'Votre code PEA Radar' ELSE subject END "
        "WHERE kind IN ('verify_code', 'reset_password', 'new_device') AND status IN ('sent', 'failed')"
    ).bindparams(erased=ERASED))


def downgrade() -> None:
    pass  # un contenu effacé ne se restaure pas
