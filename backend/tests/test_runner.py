from datetime import UTC, datetime

from app.jobs.runner import run_job
from app.models import DataStatus

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)


def test_run_job_records_success(db, make_ctx):
    ctx = make_ctx(now=NOW)
    assert run_job(ctx, "demo", lambda c: 42) == 42
    status = db.get(DataStatus, "demo")
    assert status.last_success_at == NOW
    assert status.last_count == 42


def test_run_job_records_error_without_raising(db, make_ctx):
    ctx = make_ctx(now=NOW)

    def boom(c):
        raise RuntimeError("Yahoo indisponible")

    assert run_job(ctx, "demo", boom) == 0
    status = db.get(DataStatus, "demo")
    assert status.last_error_at == NOW
    assert "Yahoo indisponible" in status.last_error
