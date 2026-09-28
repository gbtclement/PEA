import logging
from datetime import timedelta

from sqlalchemy import select

from app.jobs.context import JobContext
from app.models import EmailLog

logger = logging.getLogger(__name__)
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))
BATCH_SIZE = 50


def send_pending_emails(ctx: JobContext) -> int:
    """Envoie les mails en attente dont l'heure est venue ; en cas d'échec, réessaie à 1, 5 puis 30 min."""
    if ctx.mailer is None:
        return 0
    now = ctx.now()
    sent = 0
    with ctx.session_factory() as session:
        rows = session.scalars(
            select(EmailLog)
            .where(EmailLog.status == "pending", EmailLog.next_attempt_at <= now)
            .order_by(EmailLog.id).limit(BATCH_SIZE).with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            row.attempts += 1
            try:
                ctx.mailer.send(to=row.recipient, subject=row.subject, html=row.html, text=row.text, headers=row.headers or {})
            except Exception as exc:  # serveur absent, refus, délai dépassé…
                row.error = str(exc)[:300]
                if row.attempts > len(RETRY_DELAYS):
                    row.status = "failed"
                    logger.error("Mail %s abandonné après %d essais : %s", row.id, row.attempts, row.error)
                else:
                    row.next_attempt_at = now + RETRY_DELAYS[row.attempts - 1]
                    logger.warning("Échec d'envoi du mail %s (essai %d) : %s", row.id, row.attempts, row.error)
            else:
                row.status, row.sent_at, row.error = "sent", now, None
                sent += 1
        session.commit()
    return sent
