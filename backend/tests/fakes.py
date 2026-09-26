from datetime import date

from app.providers.base import DailyBar, Fundamentals, ListedSecurity, Quote


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
    ) -> None:
        self.quotes = quotes or {}
        self.history = history or {}
        self.fundamentals = fundamentals or {}
        self.quote_calls: list[list[str]] = []
        self.history_calls: list[tuple[list[str], date]] = []
        self.fundamental_calls: list[str] = []

    def get_quotes(self, tickers: list[str]) -> dict[str, Quote]:
        self.quote_calls.append(list(tickers))
        return {t: q for t, q in self.quotes.items() if t in tickers}

    def get_daily_history(self, tickers: list[str], start: date) -> dict[str, list[DailyBar]]:
        self.history_calls.append((list(tickers), start))
        return {t: bars for t, bars in self.history.items() if t in tickers}

    def get_fundamentals(self, ticker: str) -> Fundamentals | None:
        self.fundamental_calls.append(ticker)
        return self.fundamentals.get(ticker)
