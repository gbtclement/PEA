import pytest

from app.providers.retry import with_retries


def test_retries_then_succeeds():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return "ok"

    assert with_retries(flaky, sleep=sleeps.append) == "ok"
    assert sleeps == [2.0, 4.0]


def test_raises_after_last_attempt():
    sleeps = []

    def always_fails():
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        with_retries(always_fails, attempts=3, sleep=sleeps.append)
    assert sleeps == [2.0, 4.0]
