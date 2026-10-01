import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import EmailLog
from app.services.mail.render import SUBJECTS, render


def enqueue(
    db: Session, kind: str, *, to: str, context: dict, user_id: uuid.UUID | None = None, dedupe_key: str | None = None,
    headers: dict[str, str] | None = None,
) -> int | None:
    """Met un mail en file d'attente dans la même transaction que l'action qui le déclenche (pas de commit ici).

    Le worker l'enverra dans les secondes qui suivent. Renvoie None si `dedupe_key` a déjà été utilisée.
    """
    mail = render(kind, context, base_url=get_settings().public_base_url)
    stmt = (
        pg_insert(EmailLog)
        .values(user_id=user_id, kind=kind, recipient=to, subject=mail.subject, html=mail.html, text=mail.text,
                headers=headers or {}, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(EmailLog.id)
    )
    return db.execute(stmt).scalar_one_or_none()


# Mails qui portent un code ou un lien de connexion : une fois partis (ou abandonnés), la copie en base ne doit plus
# permettre de s'en servir. Le reste de l'historique (destinataire, type, dates, erreur) est gardé.
SECRET_KINDS = frozenset({"verify_code", "reset_password", "new_device"})
ERASED = "Contenu effacé après l'envoi : ce mail contenait un code ou un lien personnel."


def forget_secrets(row: EmailLog) -> None:
    if row.kind in SECRET_KINDS:
        row.subject = SUBJECTS[row.kind].split(" : {")[0]  # « Votre code PEA Radar : {code} » perd son code
        row.html = row.text = ERASED
    if row.kind == "account_deleted":  # le compte n'existe plus : son adresse ne reste pas en clair (spec 6.4)
        from app.services.privacy.erasure import email_fingerprint

        row.recipient = email_fingerprint(row.recipient)
