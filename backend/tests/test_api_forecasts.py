from datetime import UTC, date, datetime

import pytest

from app.models import Forecast, ForecastRun, SecurityQuote
from tests.factories import make_security


@pytest.fixture(autouse=True)
def premium_user(db, user):
    """Le contenu des prévisions est testé avec un compte Premium ; l'accès est testé dans test_api_premium_gates.py."""
    user.is_premium = True
    db.flush()


AS_OF = date(2026, 9, 25)


def stat(signal, horizon, n=1000, mean=0.01, hit=0.55):
    return {"signal": signal, "horizon": horizon, "n": n, "mean": mean, "median": mean / 2, "hit_rate": hit,
            "mean_excess": mean - 0.001, "beat_index": 0.52, "hit_after_fees": hit - 0.1, "std_excess": 0.05,
            "reliability": "moyenne", "t_stat": 2.5}


def backtest(edge):
    return {"days": 200, "picks": 2000, "hit_rate": 0.55, "hit_after_fees": 0.45, "mean_return": 0.01,
            "mean_after_fees": 0.0004, "mean_excess": 0.006, "baseline_mean": 0.01 - edge, "edge": edge}


def forecast(security, horizon, rank, expected, as_of=AS_OF, actual=None, signals=("trend_strong",)):
    return Forecast(security_id=security.id, as_of=as_of, horizon=horizon, expected_return=expected, prob_up=0.56,
                    reliability="elevee", signals=list(signals), rank=rank, base_close=100.0, actual_return=actual,
                    resolved_on=None if actual is None else date(2026, 10, 2))


@pytest.fixture
def seeded(db):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    airbus = make_security(db, "AIR.PA", name="Airbus")
    foreign = make_security(db, "XX.PA", name="Étranger", eligibility="non_eligible")
    db.add(SecurityQuote(security_id=lvmh.id, price=612.4, previous_close=600.0, change_pct=2.07, volume=1, as_of=datetime(2026, 9, 25, 15, 35, tzinfo=UTC)))
    db.add(ForecastRun(
        computed_at=datetime(2026, 9, 27, 5, 0, tzinfo=UTC), data_until=AS_OF, cutoff=date(2025, 10, 1), round_trip_cost=0.0096,
        stats=[stat("__all__", h, n=100_000, mean=0.002, hit=0.51) for h in ("1d", "1w", "1m")]
        + [stat("trend_strong", h) for h in ("1d", "1w", "1m")] + [stat("surge_week", "1w", mean=-0.012, hit=0.42)],
        backtest={"1d": backtest(0.001), "1w": backtest(0.0035), "1m": backtest(0.0063)},
    ))
    db.add_all([
        forecast(lvmh, "1w", 2, 0.004), forecast(lvmh, "1d", 1, 0.002), forecast(lvmh, "1m", 2, 0.01),
        forecast(airbus, "1w", 1, 0.009, signals=("trend_strong", "high_52w")), forecast(airbus, "1m", 1, 0.02),
        forecast(foreign, "1w", 3, -0.01, signals=("surge_week",)),
        # une prédiction plus ancienne, vérifiée depuis
        forecast(airbus, "1w", 1, 0.008, as_of=date(2026, 9, 18), actual=0.03),
        forecast(lvmh, "1w", 2, 0.003, as_of=date(2026, 9, 18), actual=-0.01),
    ])
    db.flush()
    return {"lvmh": lvmh, "airbus": airbus, "foreign": foreign}


def test_empty_state_before_the_first_computation(client):
    assert client.get("/api/forecasts").json() == {"as_of": None, "round_trip_cost": None, "rows": []}
    signals = client.get("/api/forecasts/signals").json()
    assert signals["as_of"] is None and signals["signals"] == []
    record = client.get("/api/forecasts/track-record").json()
    assert record["simulated"] == {"1d": None, "1w": None, "1m": None}
    assert record["real"] == {"1d": None, "1w": None, "1m": None}


def test_latest_predictions_ordered_by_one_week_rank(client, seeded):
    body = client.get("/api/forecasts").json()
    assert body["as_of"] == "2026-09-25"
    assert body["round_trip_cost"] == pytest.approx(0.0096)
    names = [r["security"]["name"] for r in body["rows"]]
    assert names == ["Airbus", "LVMH", "Étranger"]
    lvmh = body["rows"][1]
    assert lvmh["security"]["price"] == pytest.approx(612.4)
    assert lvmh["security"]["eligibility"] == "eligible"
    assert lvmh["horizons"]["1d"] == {"expected_return": 0.002, "prob_up": 0.56, "reliability": "elevee", "rank": 1}
    assert body["rows"][0]["horizons"]["1d"] is None
    assert body["rows"][0]["signals"] == [
        {"key": "trend_strong", "label": "Tendance haussière forte", "bullish": True},
        {"key": "high_52w", "label": "Plus haut sur 1 an", "bullish": True},
    ]


def test_signal_statistics_table(client, seeded):
    body = client.get("/api/forecasts/signals").json()
    assert body["as_of"] == "2026-09-25"
    assert body["baseline"]["1w"]["n"] == 100_000
    keys = [s["key"] for s in body["signals"]]
    assert len(keys) == 14 and "__all__" not in keys
    trend = next(s for s in body["signals"] if s["key"] == "trend_strong")
    assert trend["label"] == "Tendance haussière forte" and trend["bullish"] is True and trend["description"]
    assert trend["horizons"]["1w"]["hit_rate"] == pytest.approx(0.55)
    breakout = next(s for s in body["signals"] if s["key"] == "breakout_20")
    assert breakout["horizons"] == {"1d": None, "1w": None, "1m": None}  # jamais observé


def test_track_record_simulated_and_real(client, seeded):
    body = client.get("/api/forecasts/track-record").json()
    assert body["cutoff"] == "2025-10-01"
    assert body["simulated"]["1m"]["edge"] == pytest.approx(0.0063)
    real = body["real"]["1w"]
    assert real["picks"] == 2
    assert real["hit_rate"] == pytest.approx(0.5)
    assert real["mean_return"] == pytest.approx(0.01)
    assert real["mean_after_fees"] == pytest.approx(0.01 - 0.0096)
    assert real["first_day"] == "2026-09-18"
    assert body["real"]["1d"] is None


def test_security_forecast(client, seeded):
    body = client.get(f"/api/securities/{seeded['airbus'].id}/forecast").json()
    assert body["as_of"] == "2026-09-25"
    assert [s["key"] for s in body["signals"]] == ["trend_strong", "high_52w"]
    assert body["horizons"]["1w"]["rank"] == 1
    assert body["horizons"]["1d"] is None


def test_security_without_forecast_and_unknown_security(client, seeded, db):
    quiet = make_security(db, "QT.PA", name="Calme")
    body = client.get(f"/api/securities/{quiet.id}/forecast").json()
    assert body == {"as_of": "2026-09-25", "signals": [], "horizons": {"1d": None, "1w": None, "1m": None}}
    assert client.get("/api/securities/999999/forecast").status_code == 404
