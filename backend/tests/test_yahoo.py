from datetime import UTC, date, datetime

import pandas as pd
import pytest

from app.providers.yahoo import (
    YahooProvider, bars_from_frame, fundamentals_from_info, quote_from_frame, split_by_ticker,
)
from app.services.market_calendar import PARIS

COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def frame(rows: list[tuple]) -> pd.DataFrame:
    """rows : (date iso, open, high, low, close, volume)"""
    df = pd.DataFrame([r[1:] for r in rows], columns=COLUMNS, index=pd.to_datetime([r[0] for r in rows]))
    df.index.name = "Date"
    return df


def multi(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(frames, axis=1)


ROWS = [("2026-09-24", 10, 11, 9, 10.0, 100), ("2026-09-25", 10, 12, 10, 11.0, 200)]


def test_split_multiindex_drops_missing_and_nan():
    nan_rows = [("2026-09-24", None, None, None, None, None), ("2026-09-25", None, None, None, None, None)]
    df = multi({"A.PA": frame(ROWS), "B.PA": frame(nan_rows)})
    result = split_by_ticker(df, ["A.PA", "B.PA", "C.PA"])
    assert list(result) == ["A.PA"]
    assert len(result["A.PA"]) == 2


def test_split_single_level_frame():
    result = split_by_ticker(frame(ROWS), ["A.PA"])
    assert list(result) == ["A.PA"]


def test_split_empty():
    assert split_by_ticker(pd.DataFrame(), ["A.PA"]) == {}


def test_bars_from_frame():
    bars = bars_from_frame(frame(ROWS))
    assert bars[0].date == date(2026, 9, 24)
    assert (bars[1].close, bars[1].volume) == (11.0, 200)


def test_quote_today_uses_fetch_time():
    fetched_at = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
    quote = quote_from_frame(frame(ROWS), fetched_at)
    assert quote.price == 11.0
    assert quote.previous_close == 10.0
    assert quote.change_pct == pytest.approx(10.0)
    assert quote.as_of == fetched_at


def test_quote_past_day_uses_close_time():
    quote = quote_from_frame(frame(ROWS), datetime(2026, 9, 27, 10, 0, tzinfo=UTC))
    assert quote.as_of == datetime(2026, 9, 25, 17, 35, tzinfo=PARIS)


def test_quote_single_row_has_no_change():
    quote = quote_from_frame(frame(ROWS[:1]), datetime(2026, 9, 24, 10, 0, tzinfo=UTC))
    assert quote.previous_close is None and quote.change_pct is None


def test_fundamentals_conversions():
    info = {"trailingPE": 18.07, "trailingEps": 33.9, "dividendYield": 3.28, "earningsGrowth": 0.008,
            "revenueGrowth": -0.029, "debtToEquity": 53.306, "profitMargins": 0.1366, "marketCap": 1.9e11,
            "sector": "Consumer Cyclical", "industry": "Luxury Goods", "currency": "EUR"}
    f = fundamentals_from_info(info)
    assert f.dividend_yield == pytest.approx(0.0328)
    assert f.debt_to_equity == pytest.approx(0.53306)
    assert f.pe == pytest.approx(18.07)
    assert (f.sector, f.industry, f.currency) == ("Consumer Cyclical", "Luxury Goods", "EUR")


def test_fundamentals_bad_values_become_none():
    f = fundamentals_from_info({"trailingPE": "Infinity", "dividendYield": None, "marketCap": float("nan")})
    assert f.pe is None and f.dividend_yield is None and f.market_cap is None


def test_get_quotes_chunks_and_pauses():
    calls, sleeps = [], []

    def fake_download(tickers, **kwargs):
        calls.append(list(tickers))
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(chunk_size=2, pause_seconds=1.5, download=fake_download, sleep=sleeps.append,
                             now=lambda: datetime(2026, 9, 25, 10, 0, tzinfo=UTC))
    quotes = provider.get_quotes(["A.PA", "B.PA", "C.PA"])
    assert calls == [["A.PA", "B.PA"], ["C.PA"]]
    assert sleeps == [1.5]
    assert set(quotes) == {"A.PA", "B.PA", "C.PA"}


def test_get_quotes_skips_failing_chunk():
    def fake_download(tickers, **kwargs):
        if "A.PA" in tickers:
            raise ConnectionError("Yahoo KO")
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(chunk_size=1, download=fake_download, sleep=lambda s: None)
    assert set(provider.get_quotes(["A.PA", "B.PA"])) == {"B.PA"}


def test_get_daily_history_passes_start():
    seen = {}

    def fake_download(tickers, **kwargs):
        seen.update(kwargs)
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(download=fake_download, sleep=lambda s: None)
    history = provider.get_daily_history(["A.PA"], date(2021, 9, 28))
    assert seen["start"] == "2021-09-28"
    assert len(history["A.PA"]) == 2


def test_get_daily_history_without_start_loads_everything():
    seen = {}

    def fake_download(tickers, **kwargs):
        seen.update(kwargs)
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(download=fake_download, sleep=lambda s: None)
    provider.get_daily_history(["A.PA"], None)
    assert seen["period"] == "max" and "start" not in seen


def test_get_fundamentals_returns_none_on_error():
    def failing(ticker):
        raise ConnectionError("KO")

    provider = YahooProvider(ticker_info=failing, sleep=lambda s: None)
    assert provider.get_fundamentals("A.PA") is None


def test_get_fundamentals_ignores_near_empty_info():
    provider = YahooProvider(ticker_info=lambda t: {"trailingPegRatio": None}, sleep=lambda s: None)
    assert provider.get_fundamentals("A.PA") is None


def test_yahoo_calls_are_serialized_across_threads():
    import threading
    import time as pytime

    active, peak, guard = [0], [0], threading.Lock()

    def slow_download(tickers, **kwargs):
        with guard:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        pytime.sleep(0.1)
        with guard:
            active[0] -= 1
        return multi({t: frame(ROWS) for t in tickers})

    provider = YahooProvider(download=slow_download, sleep=lambda s: None)
    threads = [threading.Thread(target=provider.get_quotes, args=[[f"T{i}.PA"]]) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] == 1


@pytest.mark.network
def test_real_yahoo_quote():
    quotes = YahooProvider().get_quotes(["MC.PA"])
    assert quotes["MC.PA"].price > 0


def test_fundamentals_read_size_for_pea_pme():
    f = fundamentals_from_info({"fullTimeEmployees": 1234, "totalRevenue": 2.5e8, "financialCurrency": "USD",
                                "currency": "EUR", "marketCap": 4e8})
    assert (f.employees, f.revenue, f.revenue_currency, f.currency) == (1234, 2.5e8, "USD", "EUR")


def test_fundamentals_size_missing_or_garbage():
    f = fundamentals_from_info({"fullTimeEmployees": "n/a", "totalRevenue": None})
    assert (f.employees, f.revenue, f.revenue_currency) == (None, None, None)


def test_bars_skip_infinite_or_non_positive_closes():
    # Vieilles séances ajustées par Yahoo : clôture infinie ou nulle, inutilisable (JSON, simulateur).
    rows = [("1985-01-02", None, None, None, float("inf"), 0), ("1985-01-03", 1, 1, 1, 0.0, 0), ROWS[0]]
    assert [b.date for b in bars_from_frame(frame(rows))] == [date(2026, 9, 24)]
