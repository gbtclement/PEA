from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.models import EmailLog, Favorite, Forecast, Order, ScoreSnapshot, SecurityScore, UserSettings
from app.services.notifications.prefs import save_prefs
from app.services.notifications.recaps import send_weekly_recaps
from app.services.notifications.scores import notify_score_changes, take_score_snapshot
from tests.factories import make_quote, make_score, make_security

pytestmark = pytest.mark.usefixtures("app_secret")
MON, TUE = date(2026, 9, 28), date(2026, 9, 29)


def _mails(db, kind):
    return db.scalars(select(EmailLog).where(EmailLog.kind == kind)).all()


def _set_total(db, security, total, top=True):
    score = db.get(SecurityScore, security.id)
    score.total, score.eligible_for_top = total, top
    db.flush()


def test_snapshot_keeps_totals_and_top_ranks(db):
    a, b = make_security(db, "A.PA"), make_security(db, "B.PA")
    make_score(db, a, total=80.0)
    make_score(db, b, total=50.0, eligible_for_top=False)
    take_score_snapshot(db, MON)
    take_score_snapshot(db, MON)  # rejouée : remplace, sans doublon
    rows = {r.security_id: r for r in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == MON))}
    assert (rows[a.id].total, rows[a.id].top_rank, rows[b.id].top_rank) == (80.0, 1, None)
    assert rows[a.id].top_pool is True and rows[b.id].top_pool is False


def test_favorites_entering_the_top_or_moving_10_points(db, user):
    save_prefs(db, user.id, {"score_change": True})
    entering = make_security(db, "IN.PA", name="Entrant")
    jumping = make_security(db, "UP.PA", name="Bondissant")
    calm = make_security(db, "CALM.PA", name="Calme")
    stranger = make_security(db, "OUT.PA", name="Pas favori")
    make_score(db, entering, total=40.0, eligible_for_top=False)
    make_score(db, jumping, total=30.0, eligible_for_top=False)
    make_score(db, calm, total=60.0, eligible_for_top=False)
    make_score(db, stranger, total=20.0, eligible_for_top=False)
    db.add_all(Favorite(user_id=user.id, security_id=s.id) for s in (entering, jumping, calm))
    take_score_snapshot(db, MON)
    _set_total(db, entering, 70.0, top=True)
    _set_total(db, jumping, 42.0, top=False)
    _set_total(db, calm, 65.0, top=False)
    _set_total(db, stranger, 90.0, top=True)
    take_score_snapshot(db, TUE)
    assert notify_score_changes(db, TUE) == 1
    assert notify_score_changes(db, TUE) == 0  # une fois par jour
    [mail] = _mails(db, "score_change")
    assert "Entrant : entre dans le top 10" in mail.text and "Bondissant : gagne 12 points" in mail.text
    assert "Calme" not in mail.text and "Pas favori" not in mail.text


def test_no_previous_snapshot_no_mail(db, user):
    save_prefs(db, user.id, {"score_change": True})
    a = make_security(db, "A.PA")
    make_score(db, a)
    db.add(Favorite(user_id=user.id, security_id=a.id))
    take_score_snapshot(db, MON)
    assert notify_score_changes(db, MON) == 0


def test_weekly_recap_once_per_week(db, user):
    save_prefs(db, user.id, {"weekly_recap": True})
    old, new = make_security(db, "OLD.PA", name="Sortant"), make_security(db, "NEW.PA", name="Entrant")
    make_score(db, old, total=80.0, perf_1w=2.0)
    make_score(db, new, total=40.0, eligible_for_top=False)
    take_score_snapshot(db, date(2026, 9, 25))
    _set_total(db, old, 30.0, top=False)
    _set_total(db, new, 85.0, top=True)
    take_score_snapshot(db, date(2026, 10, 2))
    db.add(Order(user_id=user.id, security_id=old.id, trade_date=date(2026, 9, 1), side="buy", quantity=10,
                 unit_price=100, fee=1))
    make_quote(db, old, 102.0, as_of=datetime(2026, 10, 2, 15, 35, tzinfo=UTC))
    db.add(Forecast(security_id=new.id, as_of=date(2026, 9, 25), horizon="1w", expected_return=0.02, prob_up=0.6,
                    reliability="medium", signals=[], rank=1, base_close=10.0, actual_return=0.01,
                    resolved_on=date(2026, 10, 2)))
    db.flush()  # (si le modèle Forecast a d'autres colonnes obligatoires, les renseigner)
    saturday = datetime(2026, 10, 3, 7, 0, tzinfo=UTC)
    assert send_weekly_recaps(db, saturday) == 1
    assert send_weekly_recaps(db, saturday) == 0
    [mail] = _mails(db, "weekly_recap")
    assert "Entrée : Entrant" in mail.text and "Sortie : Sortant" in mail.text
    assert "1 sur 1 dans le bon sens" in mail.text and "1 020,00 €" in mail.text


def test_weekly_recap_uses_the_user_top(db, user):
    save_prefs(db, user.id, {"weekly_recap": True})
    db.merge(UserSettings(user_id=user.id, envelopes=["pea"]))
    foreign = make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US")
    pea = make_security(db, "MC.PA", name="LVMH")
    make_score(db, foreign, total=95.0)
    make_score(db, pea, total=50.0, eligible_for_top=False)
    take_score_snapshot(db, date(2026, 9, 25))  # avant la fenêtre de 6 jours du récap : c'est la photo « avant »
    _set_total(db, pea, 60.0, top=True)
    _set_total(db, foreign, 95.0, top=False)  # sort du top global, jamais entré dans le sien
    take_score_snapshot(db, date(2026, 10, 2))
    send_weekly_recaps(db, datetime(2026, 10, 3, 7, 0, tzinfo=UTC))
    [mail] = _mails(db, "weekly_recap")
    assert "Entrée : LVMH" in mail.text  # Apple, hors PEA, n'est pas dans son top
    assert "Apple" not in mail.text and "Sortie" not in mail.text


def _forget_pool(db, day):
    """Photo prise avant les enveloppes : on ne sait pas quels titres étaient candidats au top 10."""
    for row in db.scalars(select(ScoreSnapshot).where(ScoreSnapshot.day == day)):
        row.top_pool = None
    db.flush()


def test_no_false_top_entry_after_a_snapshot_without_pool(db, user):
    save_prefs(db, user.id, {"score_change": True})
    entering = make_security(db, "IN.PA", name="Entrant")
    make_score(db, entering, total=60.0, eligible_for_top=False)
    db.add(Favorite(user_id=user.id, security_id=entering.id))
    take_score_snapshot(db, MON)
    _forget_pool(db, MON)
    _set_total(db, entering, 62.0, top=True)
    take_score_snapshot(db, TUE)
    assert notify_score_changes(db, TUE) == 0  # entrée inconnue, variation trop faible


def test_weekly_recap_without_pool_before_lists_no_entries(db, user):
    save_prefs(db, user.id, {"weekly_recap": True})
    pea = make_security(db, "MC.PA", name="LVMH")
    make_score(db, pea, total=50.0, eligible_for_top=False)
    take_score_snapshot(db, date(2026, 9, 25))
    _forget_pool(db, date(2026, 9, 25))
    _set_total(db, pea, 60.0, top=True)
    take_score_snapshot(db, date(2026, 10, 2))
    send_weekly_recaps(db, datetime(2026, 10, 3, 7, 0, tzinfo=UTC))
    [mail] = _mails(db, "weekly_recap")
    assert "LVMH" not in mail.text
