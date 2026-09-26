from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataStatus


def _get_or_create(session: Session, job: str) -> DataStatus:
    status = session.get(DataStatus, job)
    if status is None:
        status = DataStatus(job=job, last_count=0)
        session.add(status)
    return status


def record_success(session: Session, job: str, count: int, at: datetime) -> None:
    status = _get_or_create(session, job)
    status.last_success_at = at
    status.last_count = count


def record_error(session: Session, job: str, message: str, at: datetime) -> None:
    status = _get_or_create(session, job)
    status.last_error_at = at
    status.last_error = message


def list_statuses(session: Session) -> list[DataStatus]:
    return list(session.scalars(select(DataStatus).order_by(DataStatus.job)))
