from datetime import UTC, datetime

import pandas as pd

from app.providers.yahoo import YahooProvider, intraday_from_frame, parse_news


def intraday_frame() -> pd.DataFrame:
    index = pd.DatetimeIndex(["2026-09-25 09:00", "2026-09-25 09:05"], tz="Europe/Paris")
    return pd.DataFrame({"Open": [10, 11], "High": [11, 12], "Low": [9, 10], "Close": [10.5, 11.5], "Volume": [100, 200]},
                        index=index)


def test_intraday_from_frame_converts_to_utc():
    bars = intraday_from_frame(intraday_frame())
    assert bars[0].time == datetime(2026, 9, 25, 7, 0, tzinfo=UTC)
    assert (bars[1].close, bars[1].volume) == (11.5, 200)


def test_get_intraday_uses_download():
    seen = {}

    def fake_download(tickers, **kwargs):
        seen.update(kwargs)
        return pd.concat({tickers[0]: intraday_frame()}, axis=1)

    provider = YahooProvider(download=fake_download, sleep=lambda s: None)
    bars = provider.get_intraday("MC.PA", "1d", "5m")
    assert (seen["period"], seen["interval"]) == ("1d", "5m")
    assert len(bars) == 2


def test_parse_news_new_format():
    items = [{"content": {"title": "LVMH publie", "pubDate": "2026-09-25T08:00:00Z",
                          "canonicalUrl": {"url": "https://ex.com/a"}, "provider": {"displayName": "Reuters"}}}]
    news = parse_news(items)
    assert news[0].title == "LVMH publie"
    assert news[0].url == "https://ex.com/a"
    assert news[0].publisher == "Reuters"
    assert news[0].published_at == datetime(2026, 9, 25, 8, 0, tzinfo=UTC)


def test_parse_news_legacy_format_and_invalid_items():
    items = [
        {"title": "Ancien format", "link": "https://ex.com/b", "publisher": "AFP", "providerPublishTime": 1790000000},
        {"content": {"title": "Sans lien"}},
        "n'importe quoi",
    ]
    news = parse_news(items)
    assert len(news) == 1
    assert news[0].publisher == "AFP" and news[0].published_at is not None


def test_get_news_returns_empty_on_error():
    def failing(ticker):
        raise ConnectionError("KO")

    provider = YahooProvider(ticker_news=failing, sleep=lambda s: None)
    assert provider.get_news("MC.PA") == []
