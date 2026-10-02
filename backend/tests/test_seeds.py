from app.seeds.loader import load_all_seeds, load_etfs, load_extra_stocks, load_indices
from app.services.envelopes.rules import EU_EEA_COUNTRIES


def test_seeds_have_unique_tickers():
    tickers = [s.yahoo_ticker for s in load_all_seeds()]
    assert len(tickers) == len(set(tickers))


def test_extra_stocks_are_in_eu_eea():
    stocks = load_extra_stocks()
    assert stocks
    for stock in stocks:
        assert stock.kind == "stock"
        assert stock.country in EU_EEA_COUNTRIES
        assert stock.yahoo_ticker.endswith((".DE", ".MC", ".HE"))


def test_etfs_and_indices_kinds():
    assert all(s.kind == "etf" and s.market == "Euronext Paris" for s in load_etfs())
    indices = load_indices()
    assert {s.yahoo_ticker for s in indices} >= {"^FCHI", "^STOXX50E"}
    assert all(s.kind == "index" for s in indices)
