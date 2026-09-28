from datetime import UTC, datetime, timedelta

from app.services.auth.codes import CodeCheck, check_code, consume_link_token, issue_code, issue_link_token
from tests.factories import make_user

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_code_ok_once(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.OK
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.INVALID  # déjà utilisé


def test_code_expires_after_15_minutes(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    assert check_code(db, user, "verify_email", code, NOW + timedelta(minutes=15)) == CodeCheck.EXPIRED


def test_sixth_attempt_fails_even_with_right_code(db):
    user = make_user(db, verified=False)
    code = issue_code(db, user, "verify_email", NOW)
    wrong = "000000" if code != "000000" else "111111"
    results = [check_code(db, user, "verify_email", wrong, NOW) for _ in range(5)]
    assert results == [CodeCheck.INVALID] * 4 + [CodeCheck.TOO_MANY]
    assert check_code(db, user, "verify_email", code, NOW) == CodeCheck.TOO_MANY


def test_new_code_cancels_previous(db):
    user = make_user(db, verified=False)
    first = issue_code(db, user, "verify_email", NOW)
    second = issue_code(db, user, "verify_email", NOW)
    if first != second:
        assert check_code(db, user, "verify_email", first, NOW) == CodeCheck.INVALID
    assert check_code(db, user, "verify_email", second, NOW) == CodeCheck.OK


def test_link_token_single_use_and_purpose_bound(db):
    user = make_user(db)
    token = issue_link_token(db, user, "reset_password", NOW, timedelta(minutes=30))
    assert consume_link_token(db, token, "not_me", NOW) is None
    assert consume_link_token(db, token, "reset_password", NOW + timedelta(minutes=31)) is None
    assert consume_link_token(db, token, "reset_password", NOW) == user
    assert consume_link_token(db, token, "reset_password", NOW) is None
