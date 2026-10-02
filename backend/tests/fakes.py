from datetime import date

from app.providers.base import DailyBar, Fundamentals, IntradayBar, ListedSecurity, NewsItem, Quote


class FakeListing:
    def __init__(self, items: list[ListedSecurity] | None = None) -> None:
        self.items = items or []
        self.calls = 0

    def fetch_listed(self) -> list[ListedSecurity]:
        self.calls += 1
        return list(self.items)


class FakeMarket:
    def __init__(
        self,
        quotes: dict[str, Quote] | None = None,
        history: dict[str, list[DailyBar]] | None = None,
        fundamentals: dict[str, Fundamentals] | None = None,
        intraday: dict[str, list[IntradayBar]] | None = None,
        news: dict[str, list[NewsItem]] | None = None,
        fail_on_demand: bool = False,
    ) -> None:
        self.quotes = quotes or {}
        self.history = history or {}
        self.fundamentals = fundamentals or {}
        self.intraday = intraday or {}
        self.news = news or {}
        self.fail_on_demand = fail_on_demand
        self.quote_calls: list[list[str]] = []
        self.history_calls: list[tuple[list[str], date | None]] = []
        self.fundamental_calls: list[str] = []
        self.intraday_calls: list[tuple[str, str, str]] = []

    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        self.quote_calls.append(list(tickers))
        return {t: q for t, q in self.quotes.items() if t in tickers}

    def get_daily_history(self, tickers: list[str], start: date | None) -> dict[str, list[DailyBar]]:
        self.history_calls.append((list(tickers), start))
        return {t: bars for t, bars in self.history.items() if t in tickers}

    def get_fundamentals(self, ticker: str) -> Fundamentals | None:
        self.fundamental_calls.append(ticker)
        return self.fundamentals.get(ticker)

    def get_intraday(self, ticker: str, period: str, interval: str) -> list[IntradayBar]:
        self.intraday_calls.append((ticker, period, interval))
        if self.fail_on_demand:
            raise ConnectionError("Yahoo KO")
        return self.intraday.get(ticker, [])

    def get_news(self, ticker: str) -> list[NewsItem]:
        if self.fail_on_demand:
            raise ConnectionError("Yahoo KO")
        return self.news.get(ticker, [])
