from datetime import UTC, date, datetime, timedelta

import pytest

from app.models import DailyPrice, SecurityQuote
from app.services.assistant.prompt import system_prompt
from app.services.assistant.tools import TOOL_LABELS, TOOL_SPECS, ToolError, run_tool
from tests.factories import make_quote, make_security, make_user


@pytest.fixture
def user(db):
    return make_user(db)


def closes(db, security, n=260, start=100.0):
    today = date.today()
    for i in range(n):
        db.add(DailyPrice(security_id=security.id, date=today - timedelta(days=n - i), close=start + i))
    db.flush()


def test_specs_are_valid_and_labelled():
    names = {t["name"] for t in TOOL_SPECS}
    assert names == {"search_securities", "get_security_overview", "get_price_history", "get_top10", "get_portfolio",
                     "simulate_past_investment"}
    for spec in TOOL_SPECS:
        assert spec["input_schema"]["type"] == "object" and spec["description"]
        assert spec["name"] in TOOL_LABELS
    assert "web_search" in TOOL_LABELS


def test_search_securities(db, user):
    make_quote(db, make_security(db, "MC.PA", name="LVMH"), 600.0)
    result = run_tool(db, user, "search_securities", {"query": "lvmh"})
    assert result[0]["ticker"] == "MC.PA" and result[0]["name"] == "LVMH"
    assert run_tool(db, user, "search_securities", {"query": "zzz"}) == []


def test_security_overview_by_symbol_or_yahoo_ticker(db, user):
    s = make_security(db, "MC.PA", name="LVMH")
    db.add(SecurityQuote(security_id=s.id, price=600, previous_close=590, change_pct=1.7, volume=1,
                         as_of=datetime(2026, 3, 10, 16, tzinfo=UTC)))
    db.flush()
    for ticker in ("MC.PA", "mc", "MC"):
        overview = run_tool(db, user, "get_security_overview", {"ticker": ticker})
        assert overview["name"] == "LVMH" and overview["price"] == 600 and overview["as_of"].startswith("2026-03-10")
        assert "sparkline" not in overview


def test_unknown_ticker_is_tool_error(db, user):
    with pytest.raises(ToolError, match="introuvable"):
        run_tool(db, user, "get_security_overview", {"ticker": "NOPE"})


def test_price_history_sampled_with_indicators(db, user):
    s = make_security(db, "MC.PA")
    closes(db, s)
    result = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "1Y"})
    assert len(result["closes"]) <= 60 and result["closes"][-1]["close"] == 359.0
    assert result["indicators"]["sma50"] is not None and result["indicators"]["rsi14"] == pytest.approx(100.0)
    assert result["performance_pct"] > 0
    with pytest.raises(ToolError):
        run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "2Y"})
    full = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "MAX"})
    month = run_tool(db, user, "get_price_history", {"ticker": "MC.PA", "period": "1M"})
    assert full["first_date"] < month["first_date"] and full["closes"][-1]["close"] == 359.0


def test_top10_and_portfolio_empty(db, user):
    assert run_tool(db, user, "get_top10", {}) == []
    portfolio = run_tool(db, user, "get_portfolio", {})
    assert portfolio["positions"] == [] and portfolio["counter"]["min_orders"] == 12


def test_simulate_past_investment(db, user):
    s = make_security(db, "MC.PA")
    closes(db, s)
    start = (date.today() - timedelta(days=100)).isoformat()
    result = run_tool(db, user, "simulate_past_investment", {"ticker": "MC.PA", "amount": 1000, "date": start})
    assert result["shares"] > 0 and result["gain"] > 0 and result["start_date"] >= start


@pytest.mark.parametrize("tool_input", [
    {"ticker": "MC.PA", "amount": -5, "date": "2026-01-02"},
    {"ticker": "MC.PA", "amount": 100, "date": "2999-01-01"},
    {"ticker": "MC.PA", "amount": 100, "date": "pas une date"},
    {"ticker": "MC.PA"},
])
def test_simulate_invalid_input_is_tool_error(db, user, tool_input):
    make_security(db, "MC.PA")
    with pytest.raises(ToolError):
        run_tool(db, user, "simulate_past_investment", tool_input)


def test_unknown_tool_is_tool_error(db, user):
    with pytest.raises(ToolError):
        run_tool(db, user, "rm_rf", {})


def test_prompt_mentions_the_chosen_envelopes():
    assert "PEA, PEA-PME" in system_prompt(date(2026, 10, 2), 12, ["pea", "pea_pme"], None)
    assert "ne suppose pas qu'il investit via un PEA" in system_prompt(date(2026, 10, 2), 12, ["cto"], None)


def test_prompt_keeps_the_pea_when_the_securities_account_is_also_ticked():
    text = system_prompt(date(2026, 10, 3), 12, ["pea", "cto"], None)
    assert "PEA, Compte-titres" in text
    assert "n'est pas filtré" in text and "ne suppose pas qu'il investit via un PEA" not in text
