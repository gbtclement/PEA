"""Suppression d'un compte (par son titulaire, par un admin ou pour inactivité), spec 6.4."""
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.models import EmailLog, StripeCancellation, Subscription, User
from app.services.mail.outbox import enqueue
from app.services.security_log import log_event

ERASED_ACCOUNT = "Contenu effacé : le compte a été supprimé."


def email_fingerprint(email: str) -> str:
    """Remplace une adresse dans les journaux : reconnaître une même adresse reste possible, la lire non."""
    return f"supprimé:{token_hash(email.strip().lower())[:16]}"


def erase_account(db: Session, user: User, *, now: datetime, actor: User | None = None, reason: str = "self") -> None:
    """Supprime le compte et toutes ses données (ON DELETE CASCADE), puis met le mail C6 en file. Pas de commit ici.

    Le journal de sécurité et l'historique des mails gardent leurs lignes, sans lien vers le compte ni adresse en clair.
    L'abonnement Stripe vivant est mis en file de résiliation ; les lignes subscriptions et billing_consents partent avec
    le compte.
    """
    email, first_name = user.email, user.first_name
    # Écrite avant la suppression : son user_id passera à NULL (ON DELETE SET NULL), l'acteur éventuel reste.
    if actor is not None:
        log_event(db, "admin_user_deleted", now=now, user_id=user.id, actor_id=actor.id)
    else:
        log_event(db, "account_deleted", now=now, user_id=user.id, details={"reason": reason})
    db.execute(delete(EmailLog).where(EmailLog.user_id == user.id, EmailLog.status == "pending"))
    for row in db.scalars(select(EmailLog).where(EmailLog.user_id == user.id)):  # chaque ligne garde SA propre empreinte
        if not row.recipient.startswith("supprimé:"):
            row.recipient = email_fingerprint(row.recipient)
        row.html = row.text = ERASED_ACCOUNT  # montants, titres et prénom ne restent pas
    sub = db.get(Subscription, user.id)
    if sub is not None and sub.stripe_subscription_id and sub.status not in ("canceled", "incomplete_expired"):
        # Résilié par le worker dès que Stripe répond (Ruling 1) : plus aucun prélèvement après la suppression.
        db.merge(StripeCancellation(subscription_id=sub.stripe_subscription_id))
    db.flush()
    db.delete(user)
    db.flush()
    enqueue(db, "account_deleted", to=email, user_id=None, context={"first_name": first_name})
