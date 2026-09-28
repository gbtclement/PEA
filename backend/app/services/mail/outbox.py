import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailLog
from app.services.mail.render import render


def enqueue(
    db: Session, kind: str, *, to: str, context: dict, user_id: uuid.UUID | None = None, dedupe_key: str | None = None,
) -> int | None:
    """Met un mail en file d'attente dans la même transaction que l'action qui le déclenche (pas de commit ici).

    Le worker l'enverra dans les secondes qui suivent. Renvoie None si `dedupe_key` a déjà été utilisée.
    """
    mail = render(kind, context, base_url=get_settings().public_base_url)
    stmt = (
        pg_insert(EmailLog)
        .values(user_id=user_id, kind=kind, recipient=to, subject=mail.subject, html=mail.html, text=mail.text,
                headers={}, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(EmailLog.id)
    )
    return db.execute(stmt).scalar_one_or_none()
