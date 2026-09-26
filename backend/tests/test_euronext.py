from pathlib import Path

import pytest

from app.providers.euronext import EuronextListingProvider, parse_euronext_csv, yahoo_ticker_for

SAMPLE = Path(__file__).parent / "fixtures" / "euronext_sample.csv"


def sample_text() -> str:
    return SAMPLE.read_text(encoding="utf-8")


@pytest.mark.parametrize("symbol, market, expected", [
    ("MC", "Euronext Paris", "MC.PA"),
    ("AL2SI", "Euronext Growth Paris", "AL2SI.PA"),
    ("SOLB", "Euronext Brussels, Paris", "SOLB.BR"),
    ("2020", "Oslo Børs", "2020.OL"),
    ("1MMM", "Euronext Global Equity Market", None),
    ("4MMM", "EuroTLX", None),
])
def test_yahoo_ticker_for(symbol, market, expected):
    assert yahoo_ticker_for(symbol, market) == expected


def test_parse_keeps_supported_markets_only():
    tickers = {s.yahoo_ticker for s in parse_euronext_csv(sample_text())}
    assert tickers == {"2020.OL", "AL2SI.PA", "AGS.BR", "DUAL.PA", "MC.PA", "SOLB.BR"}


def test_parse_deduplicates_isin_by_market_priority():
    duals = [s for s in parse_euronext_csv(sample_text()) if s.isin == "FR0000000001"]
    assert len(duals) == 1
    assert duals[0].yahoo_ticker == "DUAL.PA"
    assert duals[0].market == "Euronext Paris"


def test_parse_fields():
    lvmh = next(s for s in parse_euronext_csv(sample_text()) if s.isin == "FR0000121014")
    assert (lvmh.name, lvmh.symbol, lvmh.market) == ("LVMH", "MC", "Euronext Paris")


def test_parse_handles_missing_bom():
    assert len(parse_euronext_csv(sample_text().lstrip("﻿"))) == 6


def test_parse_rejects_unexpected_format():
    with pytest.raises(ValueError):
        parse_euronext_csv("<html>Maintenance</html>")


def test_provider_uses_download_when_available():
    provider = EuronextListingProvider("http://x", snapshot_path=Path("/nonexistent"),
                                       http_post=lambda url, data: sample_text(), sleep=lambda s: None, min_rows=1)
    assert len(provider.fetch_listed()) == 6


def test_provider_falls_back_on_truncated_download(tmp_path):
    truncated = "\n".join(sample_text().splitlines()[:6])  # en-têtes + 2 lignes seulement
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_text(sample_text(), encoding="utf-8")
    provider = EuronextListingProvider("http://x", snapshot_path=snapshot,
                                       http_post=lambda url, data: truncated, sleep=lambda s: None, min_rows=5)
    assert len(provider.fetch_listed()) == 6


def test_provider_falls_back_on_http_error():
    def failing(url, data):
        raise ConnectionError("réseau coupé")

    provider = EuronextListingProvider("http://x", snapshot_path=SAMPLE, http_post=failing, sleep=lambda s: None)
    assert len(provider.fetch_listed()) == 6


def test_provider_falls_back_on_html():
    provider = EuronextListingProvider("http://x", snapshot_path=SAMPLE,
                                       http_post=lambda url, data: "<html>Maintenance</html>", sleep=lambda s: None)
    assert len(provider.fetch_listed()) == 6
