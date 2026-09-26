import logging
from collections.abc import Callable

from app.jobs.context import JobContext
from app.repositories.data_status import record_error, record_success

logger = logging.getLogger(__name__)


def run_job(ctx: JobContext, name: str, fn: Callable[[JobContext], int]) -> int:
    """Exécute une tâche et consigne son résultat dans `data_status`, sans jamais lever d'exception."""
    logger.info("Début de la tâche %s", name)
    try:
        count = fn(ctx)
    except Exception as exc:
        logger.exception("Échec de la tâche %s", name)
        with ctx.session_factory() as session:
            record_error(session, name, str(exc)[:1000], ctx.now())
            session.commit()
        return 0
    with ctx.session_factory() as session:
        record_success(session, name, count, ctx.now())
        session.commit()
    logger.info("Fin de la tâche %s (%d éléments)", name, count)
    return count
