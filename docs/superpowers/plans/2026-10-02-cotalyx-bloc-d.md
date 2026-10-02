# Cotalyx bloc D — Univers étendu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow the universe from ~1,900 to ~20,000 securities (Euronext ETFs, Xetra, SIX, Nasdaq Nordic, United States) with real FX rates, one trading calendar per place, and a first load that runs in the background.

**Architecture:** Each place is a `ListingProvider` with a `source` name, a live fetch and a normalized CSV snapshot fallback (`app/seeds/listings/<source>.csv`). `refresh_universe` merges every source, keeps one listing per ISIN (home place first, then source priority) and only deactivates the securities of sources that answered. FX rates come from Yahoo once a day into `fx_rates`, with the last known value (then a fixed table) as fallback. `market_calendar` gains a `Calendar` per place (Europe, New York); quote tiers only fetch securities whose place is open, and a 22:30 evening pass handles US closes. New securities get their prices through the batched backfill, which now takes the heavy-jobs lock one batch at a time.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, APScheduler, httpx, yfinance; React 19, TanStack Query, Vitest, Playwright; Docsify.

**Spec:** `docs/superpowers/specs/2026-10-01-cotalyx-design.md` (section « Bloc D »).

## Source survey (2026-10-02, done at the start of the block as the spec asks)

| Place | Source | Live result | Decision |
|---|---|---|---|
| Euronext stocks | existing POST CSV | ~1,800 | unchanged |
| Euronext ETFs | `POST https://live.euronext.com/en/pd_es/data/track/download?mics=XPAR,XAMS,XBRU,XMIL,XLIS,XDUB,XOSL,ETFP` (same form as stocks; `dm_all_track` returns no rows) | 3,083 rows, same CSV layout as stocks, market « ETF Plus » = Milan | live + snapshot |
| United States | `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt` | 13,296 rows → ~9,500 after exclusions (5,500 stocks, 4,000 ETFs) | live + snapshot |
| Xetra | `https://www.xetra.com/xetra-en/instruments/instruments` links to `…/t7-xetr-allTradableInstruments.csv` (path has a hash, found by regex) | 1,417 stocks (407 German) + 3,140 ETFs | live + snapshot |
| SIX | `https://www.six-group.com/sheldon/equity_issuers/v1/equity_issuers.csv` (240 issuers) and `https://www.six-group.com/fqs/ref.csv?select=ShortName,ValorSymbol,ISIN,TradingBaseCurrency,SecTypeDesc&where=PortalSegment=FU&orderby=ShortName&page=1&pagesize=99999` (2,326 « Exchange Traded Fund ») | ok | live + snapshot |
| Nasdaq Nordic | `https://api.nasdaq.com/api/nordic/screener/shares?category={MAIN_MARKET,FIRST_NORTH}&tableonly=false&market={STO,HEL,CPH,ICE}` (JSON, ISIN + currency) | ~1,000 | live + snapshot |
| London | xlsx whose URL changes every month (`Instrument list_63.xlsx`), page rendered in JS | no stable URL | **postponed**, signalled in docs |
| Madrid | HTML pages only (`Empresas.aspx`) | no CSV/JSON | **postponed**; the 34 hand-picked Madrid stocks of `extra_stocks.csv` stay |
| Vienna | HTML only | no CSV/JSON | **postponed** (Austrian stocks traded on Xetra are kept, see merge rule) |
| Warsaw | gpw.pl unreachable (timeout) | — | **postponed** |

Yahoo tickers checked live: `SAP.DE`, `EUNL.DE`, `MAERSK-B.CO`, `AAK.ST`, `NOKIA.HE`, `ABBN.SW`, `CSSPX.SW` (USD), `EBND.MI`, `AGED.AS`, `BRK-B`, `AGM-A`, `AAPL`, `SPY`, `EURUSD=X`, `EURGBP=X`, `EURCHF=X`, `EURPLN=X`. Some Xetra mnemonics are unknown to Yahoo (`RAW.DE`): such securities never get a price and stay hidden from lists.

## Global Constraints

- Branch `univers-etendu`, created from `master`; PR against `master` at the end. Stop after the block.
- Interface text, comments and docs in French; commits in English (conventional commits), ending with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- Never open or print `.env`. Never modify an existing Alembic migration (new head on top of `d7f9b1c3e5a7`).
- Do not modify files under `.superpowers/` or `docs/superpowers/` except this plan and its ledger.
- The user validated the database size (5–10 GB for `daily_prices`) on 2026-10-02: full history for every security, no 10-year cap for ETFs.
- A source that fails (live and snapshot) never deactivates its securities; other sources still refresh.
- Stocks: PEA rule by ISIN unchanged. ETFs: eligible to PEA only if confirmed (`seeds/etfs.csv`, admin override) or if the name contains the word « PEA »; otherwise « à vérifier ». Never deduced from the issuer country.
- FX: Yahoo `EUR{XXX}=X` (units of XXX per euro) once a day, stored in `fx_rates`; fallback = last stored value, then the fixed table. Pence: `GBp`/`GBX` = GBP / 100.
- Calendars: Europe = current Paris hours and Euronext holidays; United States = 9:30–16:00 New York time (15:30–22:00 Paris most of the year), NYSE holidays. US evening pass at 22:30 Paris.
- Fundamentals: spread over the week (a fifth of the stocks each weekday, oldest first, never-fetched first).
- Securities without any quote do not appear in lists (Explorer, search).
- Test commands:
  - backend: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q` (one file: append the path);
  - frontend (in `frontend/`): `npx tsc -b`, `npx vitest run`, `npx oxlint` (add `< /dev/null`);
  - API types: `npm run gen:api` (dev API on :8000 must run the new code: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build api` first);
  - e2e: `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build api worker web` then `npm run e2e` in `frontend/`; afterwards restore with `docker compose up -d --build api worker web`.

## Review Focus

1. A source down (live and snapshot) must leave its securities active while the others refresh, and the job still reports the failure. Test: `test_failed_source_keeps_its_securities` (Task 6).
2. The same ISIN listed on several places must give one security, on its home place (SAP on Xetra, not a foreign copy; an Irish ETF on Euronext Paris before Xetra/SIX); a US stock on Xetra must not duplicate the US listing. Tests: `test_merge_prefers_home_listing`, `test_merge_drops_secondary_listing_of_covered_country` (Task 6).
3. The US/Europe daylight-saving gap (2nd Sunday of March → last Sunday of March): New York opens at 14:30 Paris. Test: `test_us_open_during_dst_gap` (Task 1).
4. A Yahoo FX failure must not reset conversions to 1:1 nor erase stored rates. Test: `test_refresh_fx_keeps_last_rates_when_yahoo_fails` (Task 3).
5. The first load of ~18,000 new securities must not hold the heavy-jobs lock for hours nor run twice in parallel. Tests: `test_backfill_takes_the_guard_per_batch`, `test_backfill_job_skips_when_already_running` (Task 8).

---

### Task 1: One trading calendar per place

**Files:**
- Modify: `backend/app/services/market_calendar.py`
- Test: `backend/tests/test_market_calendar.py`

**Interfaces:**
- Produces: `Calendar` (frozen dataclass: `code`, `label`, `tz`, `open`, `close`, `early_close`, `holidays`, `early_closes`; methods `is_trading_day(day)`, `close_time(day)`, `session_close(day) -> datetime`, `is_open(now) -> bool`, `last_session_close(now) -> datetime`); `EUROPE`, `US`, `CALENDARS`; `NEW_YORK`; `US_MARKETS: frozenset[str]` = {"NYSE", "NYSE American", "NYSE Arca", "Nasdaq"}; `calendar_for_market(market: str) -> Calendar`; `open_calendars(now) -> list[Calendar]`; `any_market_open(now) -> bool`; `us_holidays(year) -> set[date]`. Unchanged module functions `is_trading_day`, `is_market_open`, `last_session_close` keep meaning « Europe ».

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_market_calendar.py`)

```python
from datetime import UTC, date, datetime

from app.services.market_calendar import (
    EUROPE, PARIS, US, any_market_open, calendar_for_market, open_calendars, us_holidays,
)


def test_us_holidays_2026():
    assert us_holidays(2026) == {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
        date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    }


def test_new_year_on_saturday_is_not_moved_to_friday():
    assert date(2027, 12, 31) not in us_holidays(2027)  # 01/01/2028 est un samedi


def test_us_session_in_paris_time():
    friday = date(2026, 10, 2)
    assert not US.is_open(datetime(2026, 10, 2, 15, 29, tzinfo=PARIS))
    assert US.is_open(datetime(2026, 10, 2, 15, 30, tzinfo=PARIS))
    assert US.is_open(datetime(2026, 10, 2, 21, 59, tzinfo=PARIS))
    assert not US.is_open(datetime(2026, 10, 2, 22, 0, tzinfo=PARIS))
    assert US.session_close(friday) == datetime(2026, 10, 2, 22, 0, tzinfo=PARIS)


def test_us_open_during_dst_gap():
    # 09/03/2026 : New York est passé à l'heure d'été, pas encore Paris → ouverture à 14 h 30 heure de Paris
    assert US.is_open(datetime(2026, 3, 9, 14, 45, tzinfo=PARIS))
    assert not EUROPE.is_open(datetime(2026, 3, 9, 18, 0, tzinfo=PARIS))


def test_us_early_close_after_thanksgiving():
    assert not US.is_open(datetime(2026, 11, 27, 19, 30, tzinfo=PARIS))  # 13 h 30 à New York
    assert US.is_open(datetime(2026, 11, 27, 18, 30, tzinfo=PARIS))


def test_calendar_for_market():
    assert calendar_for_market("Nasdaq") is US
    assert calendar_for_market("NYSE Arca") is US
    assert calendar_for_market("Nasdaq Stockholm") is EUROPE
    assert calendar_for_market("Euronext Paris") is EUROPE


def test_open_calendars_and_any_market_open():
    evening = datetime(2026, 10, 2, 19, 0, tzinfo=PARIS)
    assert open_calendars(evening) == [US]
    assert any_market_open(evening)
    assert not any_market_open(datetime(2026, 10, 3, 19, 0, tzinfo=UTC))  # samedi
```

- [ ] **Step 2: Run them**

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api pytest -q tests/test_market_calendar.py`
Expected: FAIL at import (`cannot import name 'EUROPE'`).

- [ ] **Step 3: Implement** — replace `backend/app/services/market_calendar.py` with:

```python
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NEW_YORK = ZoneInfo("America/New_York")
OPEN = time(9, 0)
CLOSE = time(17, 35)
EARLY_CLOSE = time(14, 5)
US_MARKETS = frozenset({"NYSE", "NYSE American", "NYSE Arca", "Nasdaq"})


def easter_sunday(year: int) -> date:
    """Algorithme grégorien anonyme (Meeus/Jones/Butcher)."""
    # (corps actuel inchangé)


def euronext_holidays(year: int) -> set[date]:
    # (corps actuel inchangé)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_monday_of_may(year: int) -> date:
    last = date(year, 5, 31)
    return last - timedelta(days=last.weekday())


def _observed(day: date) -> date:
    """Férié tombant un samedi : chômé le vendredi ; un dimanche : le lundi."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def us_holidays(year: int) -> set[date]:
    days = {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King
        _nth_weekday(year, 2, 0, 3),  # Presidents' Day
        easter_sunday(year) - timedelta(days=2),  # Vendredi saint
        _last_monday_of_may(year),  # Memorial Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
    }
    days |= {_observed(date(year, month, day)) for month, day in ((6, 19), (7, 4), (12, 25))}
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:  # un 1er janvier un samedi n'est pas reporté au 31 décembre
        days.add(_observed(new_year))
    return days


def us_early_closes(year: int) -> set[date]:
    days = {_nth_weekday(year, 11, 3, 4) + timedelta(days=1)}
    holidays = us_holidays(year)
    days |= {d for d in (date(year, 7, 3), date(year, 12, 24)) if d.weekday() < 5 and d not in holidays}
    return days


@dataclass(frozen=True)
class Calendar:
    code: str
    label: str
    tz: ZoneInfo
    open: time
    close: time
    early_close: time
    holidays: Callable[[int], set[date]]
    early_closes: Callable[[int], set[date]]

    def is_trading_day(self, day: date) -> bool:
        return day.weekday() < 5 and day not in self.holidays(day.year)

    def close_time(self, day: date) -> time:
        return self.early_close if day in self.early_closes(day.year) else self.close

    def session_close(self, day: date) -> datetime:
        return datetime.combine(day, self.close_time(day), tzinfo=self.tz)

    def is_open(self, now: datetime) -> bool:
        local = now.astimezone(self.tz)
        return self.is_trading_day(local.date()) and self.open <= local.time() < self.close_time(local.date())

    def last_session_close(self, now: datetime) -> datetime:
        """Heure de clôture de la dernière séance terminée à l'instant `now`."""
        day = now.astimezone(self.tz).date()
        while True:
            if self.is_trading_day(day) and self.session_close(day) <= now:
                return self.session_close(day)
            day -= timedelta(days=1)


EUROPE = Calendar("europe", "Europe", PARIS, OPEN, CLOSE, EARLY_CLOSE, euronext_holidays,
                  lambda year: {date(year, 12, 24), date(year, 12, 31)})
US = Calendar("us", "New York", NEW_YORK, time(9, 30), time(16, 0), time(13, 0), us_holidays, us_early_closes)
CALENDARS = (EUROPE, US)


def calendar_for_market(market: str) -> Calendar:
    return US if market in US_MARKETS else EUROPE


def open_calendars(now: datetime) -> list[Calendar]:
    return [calendar for calendar in CALENDARS if calendar.is_open(now)]


def any_market_open(now: datetime) -> bool:
    return bool(open_calendars(now))


# Fonctions historiques : elles parlent de la séance européenne (Paris).
def is_trading_day(day: date) -> bool:
    return EUROPE.is_trading_day(day)


def is_market_open(now: datetime) -> bool:
    return EUROPE.is_open(now)


def last_session_close(now: datetime) -> datetime:
    return EUROPE.last_session_close(now)
```

Keep `_close_time` callers working: `grep -rn "_close_time\|EARLY_CLOSE\|CLOSE\b" backend/app` — `jobs/market.py` imports `CLOSE` (still exported; it is replaced in Task 7).

- [ ] **Step 4: Run** the calendar file, then the whole backend suite.

Expected: all PASS (existing Europe tests unchanged).

- [ ] **Step 5: Commit** — `feat: trading calendar per place (Europe, New York)`

---

### Task 2: Listing model — currency, source, FX table

**Files:**
- Modify: `backend/app/providers/base.py` (`ListedSecurity`, `ListingProvider`), `backend/app/providers/euronext.py` (currency column, `source`), `backend/app/models/security.py`, `backend/app/models/__init__.py`
- Create: `backend/app/models/fx.py`, `backend/alembic/versions/e3b5d7f9a1c3_universe_sources.py`
- Test: `backend/tests/test_euronext.py`, `backend/tests/test_migration_universe_sources.py`

**Interfaces:**
- Produces:
  - `ListedSecurity(isin: str | None, symbol, name, market, yahoo_ticker, kind: str = "stock", currency: str | None = None)`
  - `ListingProvider` protocol: attribute `source: str` + `fetch_listed()`
  - `EuronextListingProvider.source == "euronext"`; `parse_euronext_csv(text, kind="stock")` reads the « Currency » column (index 4) when present
  - `Security.currency: str | None` (String(8)), `Security.source: str | None` (String(16))
  - `FxRate(currency: str PK String(8), rate_to_eur: float, updated_at: datetime)` table `fx_rates`
  - Migration backfills `source`: `'euronext'` for stocks whose market starts with `Euronext` or `Oslo`, `'seed'` for the rest.

- [ ] **Step 1: Failing tests**

`backend/tests/test_euronext.py` (append):

```python
def test_parse_reads_currency_and_kind():
    text = SAMPLE.replace('"Euronext Paris";EUR', '"Euronext Paris";USD', 1)  # SAMPLE : en-tête + lignes du fichier de test
    listed = parse_euronext_csv(text, kind="etf")
    assert {s.kind for s in listed} == {"etf"}
    assert "USD" in {s.currency for s in listed}
    assert EuronextListingProvider("http://x").source == "euronext"


def test_etf_plus_maps_to_milan():
    assert yahoo_ticker_for("EBND", "ETF Plus") == "EBND.MI"
```

Adapt `SAMPLE` to the module's existing sample constant name (read the file first; if lines lack a currency column, build the text inline with `Name;ISIN;Symbol;Market;Currency` rows).

`backend/tests/test_migration_universe_sources.py`: copy `test_migration_history_complete.py` with `PREVIOUS = "d7f9b1c3e5a7"`, `NAME = "pea_radar_migration_sources_test"`, insert one `Euronext Paris` stock, one `Xetra` stock and one ETF before upgrading, then assert `source` = `euronext`, `seed`, `seed`, `currency IS NULL`, and `SELECT count(*) FROM fx_rates` = 0; downgrade back.

- [ ] **Step 2: Run** both files. Expected: FAIL (`unexpected keyword 'kind'`, migration head missing).

- [ ] **Step 3: Implement**

`providers/base.py`:

```python
@dataclass(frozen=True)
class ListedSecurity:
    isin: str | None  # absent de la liste américaine
    symbol: str
    name: str
    market: str
    yahoo_ticker: str
    kind: str = "stock"  # stock | etf
    currency: str | None = None


class ListingProvider(Protocol):
    source: str  # nom de la source (euronext, us, xetra…), rangé sur chaque titre

    def fetch_listed(self) -> list[ListedSecurity]: ...
```

`providers/euronext.py`: append `"ETF Plus": ".MI"` at the end of `MARKET_SUFFIXES` (lowest priority); `parse_euronext_csv(text: str, kind: str = "stock")` builds `ListedSecurity(isin=isin, symbol=symbol, name=name, market=primary, yahoo_ticker=ticker, kind=kind, currency=(row[4].strip() or None) if len(row) > 4 else None)`; `class EuronextListingProvider: source = "euronext"`.

`models/security.py`: after `market`:

```python
    currency: Mapped[str | None] = mapped_column(String(8))  # devise de cotation (GBp possible) ; vide = selon la place
    source: Mapped[str | None] = mapped_column(String(16))  # liste d'origine : euronext, euronext_etf, us, xetra, six, nordic, seed
```

`models/fx.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FxRate(Base):
    """Valeur en euros d'une unité de devise, mise à jour chaque jour depuis Yahoo."""

    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(8), primary_key=True)
    rate_to_eur: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

Export `FxRate` from `models/__init__.py`.

Migration `e3b5d7f9a1c3_universe_sources.py` (`down_revision = "d7f9b1c3e5a7"`):

```python
def upgrade() -> None:
    op.add_column("securities", sa.Column("currency", sa.String(8), nullable=True))
    op.add_column("securities", sa.Column("source", sa.String(16), nullable=True))
    op.execute("UPDATE securities SET source = CASE WHEN kind = 'stock' AND (market LIKE 'Euronext%' OR market LIKE 'Oslo%') "
               "THEN 'euronext' ELSE 'seed' END")
    op.create_table(
        "fx_rates",
        sa.Column("currency", sa.String(8), primary_key=True),
        sa.Column("rate_to_eur", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fx_rates")
    op.drop_column("securities", "source")
    op.drop_column("securities", "currency")
```

- [ ] **Step 4: Run** both files, then the full backend suite. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: listing currency and source, fx_rates table`

---

### Task 3: Daily FX rates and security currency

**Files:**
- Modify: `backend/app/services/fx.py`, `backend/app/jobs/scheduler.py`, `backend/app/jobs/worker.py`, `backend/app/main.py`
- Modify (currency of a security): `backend/app/api/routes/notifications.py:36`, `backend/app/api/routes/security_detail.py:59,176`, `backend/app/jobs/forecasts.py:25-29` (+ `repositories/forecasts.py` `stock_markets`), `backend/app/jobs/scoring.py:93`, `backend/app/services/portfolio_value.py:16`, `backend/app/services/notifications/moves.py:41`, `backend/app/services/notifications/price_alerts.py:67`
- Create: `backend/app/repositories/fx.py`, `backend/app/jobs/fx.py`
- Test: `backend/tests/test_fx.py`, `backend/tests/test_scheduler.py`, `backend/tests/test_fees_fx.py` (existing fx tests keep passing)

**Interfaces:**
- Consumes: `FxRate`, `Security.currency` (Task 2).
- Produces:
  - `fx.FALLBACK_TO_EUR`, `fx.FX_PAIRS: dict[str, str]` (code → `EUR{code}=X`), `fx.rate_to_eur(currency) -> float | None`, `fx.to_eur(value, currency)` (unknown currency still treated as 1:1, as today), `fx.set_rates(dict)`, `fx.use_store(loader | None)`, `fx.reset()`, `fx.currency_for_market(market)`, `fx.security_currency(security) -> str`
  - `repositories.fx.save_rates(session, rates)`, `repositories.fx.load_rates(session) -> dict[str, float]`, `repositories.fx.store_loader(session_factory) -> Callable[[], dict[str, float]]`
  - `jobs.fx.refresh_fx(ctx) -> int`; job name `"fx"`, run first in `daily_job`, `evening_job`, `us_evening_job` (Task 7) and `bootstrap_job`.

- [ ] **Step 1: Failing tests** — `backend/tests/test_fx.py`:

```python
from datetime import UTC, datetime

import pytest

from app.jobs.fx import refresh_fx
from app.models import FxRate
from app.providers.base import Quote
from app.repositories.fx import load_rates
from app.services import fx
from tests.factories import make_security
from tests.fakes import FakeMarket


@pytest.fixture(autouse=True)
def _fresh_rates():
    fx.reset()
    yield
    fx.reset()


def quote(price: float) -> Quote:
    return Quote(price, None, None, None, datetime(2026, 10, 2, 16, 0, tzinfo=UTC))


def test_pence_are_hundredths_of_pounds():
    fx.set_rates({"GBP": 1.2})
    assert fx.to_eur(250.0, "GBp") == pytest.approx(3.0)
    assert fx.to_eur(250.0, "GBX") == pytest.approx(3.0)
    assert fx.to_eur(2.5, "GBP") == pytest.approx(3.0)


def test_fallback_table_without_store():
    assert fx.to_eur(100.0, "USD") == pytest.approx(100 * fx.FALLBACK_TO_EUR["USD"])
    assert fx.to_eur(100.0, None) == 100.0
    assert fx.to_eur(100.0, "XYZ") == 100.0  # devise inconnue : comptée en euros, comme avant


def test_store_is_read_and_cached(monkeypatch):
    calls = []
    fx.use_store(lambda: calls.append(1) or {"USD": 0.5})
    assert fx.to_eur(10.0, "USD") == 5.0
    assert fx.to_eur(10.0, "USD") == 5.0
    assert len(calls) == 1


def test_broken_store_keeps_previous_rates():
    fx.use_store(lambda: (_ for _ in ()).throw(RuntimeError("base KO")))
    assert fx.to_eur(100.0, "USD") == pytest.approx(100 * fx.FALLBACK_TO_EUR["USD"])


def test_refresh_fx_stores_inverted_rates(db, make_ctx):
    market = FakeMarket(quotes={"EURUSD=X": quote(1.25), "EURGBP=X": quote(0.8)})
    assert refresh_fx(make_ctx(market=market)) == 2
    assert load_rates(db) == {"USD": pytest.approx(0.8), "GBP": pytest.approx(1.25)}
    assert fx.to_eur(10.0, "USD") == pytest.approx(8.0)


def test_refresh_fx_keeps_last_rates_when_yahoo_fails(db, make_ctx):
    refresh_fx(make_ctx(market=FakeMarket(quotes={"EURUSD=X": quote(1.25)})))
    with pytest.raises(RuntimeError):
        refresh_fx(make_ctx(market=FakeMarket(quotes={})))
    assert db.get(FxRate, "USD").rate_to_eur == pytest.approx(0.8)
    assert fx.to_eur(10.0, "USD") == pytest.approx(8.0)


def test_security_currency_prefers_the_listing(db):
    us = make_security(db, "AAPL", market="Nasdaq")
    assert fx.security_currency(us) == "USD"
    us.currency = "EUR"
    assert fx.security_currency(us) == "EUR"
    assert fx.currency_for_market("Nasdaq Stockholm") == "SEK"
    assert fx.currency_for_market("Oslo Børs") == "NOK"
```

Check `FakeMarket.__init__` for the quotes parameter name and `make_security` for `market=` before running; adapt the calls (not the assertions) if they differ.

- [ ] **Step 2: Run** `tests/test_fx.py`. Expected: FAIL at import (`app.jobs.fx`).

- [ ] **Step 3: Implement**

`services/fx.py`:

```python
"""Conversion en euros : cours de change du jour (table fx_rates), repli sur la dernière valeur puis sur une table fixe."""
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Security

logger = logging.getLogger(__name__)

# Valeur d'une unité en euros (octobre 2026), utilisée tant qu'aucun cours du jour n'est connu.
FALLBACK_TO_EUR: dict[str, float] = {
    "EUR": 1.0, "USD": 0.89, "GBP": 1.17, "CHF": 1.07, "SEK": 0.087, "DKK": 0.134, "NOK": 0.085, "PLN": 0.23,
    "ISK": 0.0066,
}
FX_PAIRS: dict[str, str] = {code: f"EUR{code}=X" for code in FALLBACK_TO_EUR if code != "EUR"}
_PENCE = ("GBp", "GBX")  # cotations londoniennes en pence
CACHE_SECONDS = 600
MARKET_CURRENCIES: dict[str, str] = {
    "NYSE": "USD", "NYSE American": "USD", "NYSE Arca": "USD", "Nasdaq": "USD",
    "SIX Swiss Exchange": "CHF", "Nasdaq Stockholm": "SEK", "Nasdaq Copenhagen": "DKK", "Nasdaq Iceland": "ISK",
}

_rates: dict[str, float] = dict(FALLBACK_TO_EUR)
_loader: Callable[[], dict[str, float]] | None = None
_loaded_at = float("-inf")


def use_store(loader: Callable[[], dict[str, float]] | None) -> None:
    """Branche la lecture des cours stockés (API et worker) ; relue au plus toutes les 10 minutes."""
    global _loader, _loaded_at
    _loader, _loaded_at = loader, float("-inf")


def set_rates(rates: dict[str, float]) -> None:
    _rates.update(rates)


def reset() -> None:
    global _loader, _loaded_at
    _rates.clear()
    _rates.update(FALLBACK_TO_EUR)
    _loader, _loaded_at = None, float("-inf")


def _current() -> dict[str, float]:
    global _loaded_at
    if _loader is not None and time.monotonic() - _loaded_at > CACHE_SECONDS:
        _loaded_at = time.monotonic()
        try:
            _rates.update(_loader())
        except Exception:
            logger.warning("Cours de change illisibles, dernières valeurs conservées", exc_info=True)
    return _rates


def rate_to_eur(currency: str | None) -> float | None:
    if currency in _PENCE:
        pound = _current().get("GBP")
        return pound / 100 if pound is not None else None
    return _current().get((currency or "EUR").upper())


def to_eur(value: float | None, currency: str | None) -> float | None:
    if value is None:
        return None
    rate = rate_to_eur(currency)
    return value * (rate if rate is not None else 1.0)


def currency_for_market(market: str) -> str:
    if "Oslo" in market:
        return "NOK"
    return MARKET_CURRENCIES.get(market, "EUR")


def security_currency(security: "Security") -> str:
    return security.currency or currency_for_market(security.market)
```

`repositories/fx.py`:

```python
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import FxRate


def save_rates(session: Session, rates: dict[str, float]) -> None:
    if not rates:
        return
    stmt = pg_insert(FxRate).values([{"currency": code, "rate_to_eur": rate} for code, rate in rates.items()])
    session.execute(stmt.on_conflict_do_update(
        index_elements=["currency"], set_={"rate_to_eur": stmt.excluded.rate_to_eur, "updated_at": func.now()},
    ))


def load_rates(session: Session) -> dict[str, float]:
    return {code: rate for code, rate in session.execute(select(FxRate.currency, FxRate.rate_to_eur))}


def store_loader(session_factory: Callable[[], AbstractContextManager[Session]]) -> Callable[[], dict[str, float]]:
    def load() -> dict[str, float]:
        with session_factory() as session:
            return load_rates(session)
    return load
```

`jobs/fx.py`:

```python
from app.jobs.context import JobContext
from app.repositories.fx import save_rates
from app.services import fx


def refresh_fx(ctx: JobContext) -> int:
    """Cours de change du jour : Yahoo donne le nombre d'unités pour un euro (EURUSD=X = 1,13)."""
    quotes = ctx.market.get_quotes(sorted(fx.FX_PAIRS.values()))
    rates = {code: 1 / q.price for code, pair in fx.FX_PAIRS.items() if (q := quotes.get(pair)) and q.price > 0}
    if not rates:
        raise RuntimeError("Cours de change indisponibles : dernières valeurs conservées")
    with ctx.session_factory() as session:
        save_rates(session, rates)
        session.commit()
    fx.set_rates(rates)
    return len(rates)
```

Wiring:
- `jobs/worker.py` `main()`: `fx.use_store(store_loader(get_session_factory()))` before `build_scheduler(...)`.
- `main.py` `create_app()`: `fx.use_store(store_loader(get_session_factory()))` (import `get_session_factory` from `app.core.db`; check its name there).
- `jobs/scheduler.py`: `run_job(ctx, "fx", refresh_fx)` as the first call inside the lock of `daily_job`, `evening_job`, and in `bootstrap_job` right after the universe step.
- Replace every `currency_for_market(x.market)` on a security with `security_currency(x)` in the listed files. In `jobs/forecasts.py`, `_inputs` receives `currencies: dict[int, str]` built by a new `stock_currencies(session)` in `repositories/forecasts.py` (same query as `stock_markets`, returning `security_currency(security)`; delete `stock_markets` if no caller remains) and uses `to_eur(1.0, currencies.get(sid))`.
- `tests/test_scheduler.py`: add `"fx"` where the tests list the jobs run by `daily_job`, `evening_job` and `bootstrap_job` (read the assertions; keep their intent).

- [ ] **Step 4: Run** `tests/test_fx.py`, then the full backend suite. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: daily FX rates from Yahoo with stored fallback`

---

### Task 4: Listing sources — snapshot base, Euronext ETFs, United States

**Files:**
- Create: `backend/app/providers/listing_source.py`, `backend/app/providers/us.py`
- Modify: `backend/app/providers/euronext.py` (`EuronextEtfListingProvider`)
- Create dir: `backend/app/seeds/listings/` (snapshots arrive in Task 5)
- Test: `backend/tests/test_listing_sources.py`

**Interfaces:**
- Consumes: `ListedSecurity` (Task 2), `with_retries`.
- Produces:
  - `listing_source.SNAPSHOT_DIR`, `SNAPSHOT_FIELDS = ("isin", "symbol", "name", "market", "yahoo_ticker", "kind", "currency")`, `write_snapshot(path, items)`, `read_snapshot(path) -> list[ListedSecurity]`
  - `class SourceListing`: class attrs `source: str`, `min_rows: int`; `__init__(self, http_get: Callable[[str], str] | None = None, sleep=time.sleep, snapshot_path: Path | None = None)`; abstract `fetch_live() -> list[ListedSecurity]`; `fetch_listed()` = live with retries and `min_rows`, else snapshot (missing/empty snapshot → raises); `_get(url) -> str` (injected or httpx GET with a browser User-Agent, 60 s)
  - `EuronextEtfListingProvider(SourceListing)`: `source = "euronext_etf"`, `min_rows = 1000`, POST form to `EURONEXT_ETF_URL`, `parse_euronext_csv(text, kind="etf")`
  - `us.parse_nasdaq_traded(text) -> list[ListedSecurity]`, `UsListingProvider(SourceListing)`: `source = "us"`, `min_rows = 5000`, `NASDAQ_TRADED_URL`

- [ ] **Step 1: Failing tests** — `backend/tests/test_listing_sources.py`:

```python
import pytest

from app.providers.base import ListedSecurity
from app.providers.euronext import EuronextEtfListingProvider
from app.providers.listing_source import SourceListing, read_snapshot, write_snapshot
from app.providers.us import UsListingProvider, parse_nasdaq_traded

NASDAQ_TRADED = """Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares
Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N
Y|BRK.B|Berkshire Hathaway Inc. New Common Stock|N| |N|100|N||BRK.B|BRK=B|N
Y|SPY|SPDR S&P 500 ETF Trust|P| |Y|100|N||SPY|SPY|N
Y|TSM|Taiwan Semiconductor Manufacturing Company Ltd. American Depositary Shares|N| |N|100|N||TSM|TSM|N
Y|AAC.U|Ares Acquisition Corporation III Units, each consisting of one Class A ordinary share|N| |N|100|N||AAC.U|AAC=|N
Y|AAC.W|Ares Acquisition Corporation III Redeemable warrants|N| |N|100|N||AAC.WS|AAC+|N
Y|AIIA.R|AI Infrastructure Acquisition Corp. Rights, each entitling the holder|N| |N|100|N||AIIAr|AIIA^|N
Y|BAC$K|Bank of America Corporation Depositary Shares Series KK Preferred|N| |N|100|N||BACpK|BAC-K|N
Y|ZZZTX|TXSE Test Stk 5 Common Stock|F| |N|40|Y||ZZZTX|ZZZTX|N
Y|ZVZZT|NASDAQ TEST STOCK|Q|G|N|100|Y|N||ZVZZT|N
Y|CBOE1|Some Cboe Listed Fund|Z| |Y|100|N||CBOE1|CBOE1|N
N|OLD|Not Traded Corp Common Stock|N| |N|100|N||OLD|OLD|N
File Creation Time: 1002202610:02|||||"""


def test_parse_nasdaq_traded_keeps_stocks_and_etfs():
    listed = {s.yahoo_ticker: s for s in parse_nasdaq_traded(NASDAQ_TRADED)}
    assert set(listed) == {"AAPL", "BRK-B", "SPY", "TSM"}
    assert (listed["AAPL"].market, listed["AAPL"].kind, listed["AAPL"].currency, listed["AAPL"].isin) == ("Nasdaq", "stock", "USD", None)
    assert (listed["SPY"].market, listed["SPY"].kind) == ("NYSE Arca", "etf")
    assert listed["BRK-B"].symbol == "BRK.B"


def test_parse_nasdaq_traded_rejects_other_files():
    with pytest.raises(ValueError):
        parse_nasdaq_traded("<html>Access denied</html>")


def test_us_provider_uses_live_file():
    provider = UsListingProvider(http_get=lambda url: NASDAQ_TRADED, sleep=lambda s: None)
    provider.min_rows = 1
    assert len(provider.fetch_listed()) == 4


def test_snapshot_round_trip(tmp_path):
    items = [ListedSecurity(None, "AAPL", "Apple", "Nasdaq", "AAPL", "stock", "USD"),
             ListedSecurity("IE00B4L5Y983", "EUNL", "iShares Core MSCI World", "Xetra", "EUNL.DE", "etf", None)]
    path = tmp_path / "x.csv"
    write_snapshot(path, items)
    assert read_snapshot(path) == items


class Broken(SourceListing):
    source = "broken"
    min_rows = 1

    def fetch_live(self):
        raise ConnectionError("KO")


def test_falls_back_to_snapshot(tmp_path):
    path = tmp_path / "broken.csv"
    write_snapshot(path, [ListedSecurity(None, "A", "A", "Nasdaq", "A", "stock", "USD")])
    assert [s.symbol for s in Broken(snapshot_path=path, sleep=lambda s: None).fetch_listed()] == ["A"]


def test_too_few_rows_uses_snapshot(tmp_path):
    path = tmp_path / "us.csv"
    write_snapshot(path, [ListedSecurity(None, "X", "X", "Nasdaq", "X", "stock", "USD")])
    provider = UsListingProvider(http_get=lambda url: NASDAQ_TRADED, sleep=lambda s: None, snapshot_path=path)
    assert [s.symbol for s in provider.fetch_listed()] == ["X"]  # 4 lignes < 5 000 : fichier tronqué


def test_no_live_and_no_snapshot_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Broken(snapshot_path=tmp_path / "absent.csv", sleep=lambda s: None).fetch_listed()


ETF_CSV = "﻿Name;ISIN;Symbol;Market;Currency;\"Open Price\"\n\"European ETFS, Funds, ETVs, ETNs. Type : ETFs\"\n\"02 Oct 2026\"\n\"All datapoints provided as of end of last active trading day.\"\n" \
    "\"AM ASIP EXJ PEA\";FR0011869312;PAEJ;\"Euronext Paris\";EUR;27.80\n" \
    "\"AB ActEBNDETFP\";LU3322521785;EBND;\"ETF Plus\";EUR;14.776\n"


def test_euronext_etf_provider_posts_the_form():
    seen = {}

    def post(url, data):
        seen.update(url=url, data=data)
        return ETF_CSV

    provider = EuronextEtfListingProvider(http_post=post, sleep=lambda s: None)
    provider.min_rows = 1
    listed = {s.yahoo_ticker: s for s in provider.fetch_listed()}
    assert set(listed) == {"PAEJ.PA", "EBND.MI"}
    assert all(s.kind == "etf" for s in listed.values())
    assert "track/download" in seen["url"] and seen["data"]["args[fe_type]"] == "csv"
```

- [ ] **Step 2: Run** `tests/test_listing_sources.py`. Expected: FAIL at import.

- [ ] **Step 3: Implement**

`providers/listing_source.py`:

```python
"""Socle commun des listes de titres : téléchargement, contrôle de taille, repli sur un instantané versionné."""
import csv
import logging
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from app.core.brand import APP_NAME
from app.providers.base import ListedSecurity
from app.providers.retry import with_retries

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "seeds" / "listings"
SNAPSHOT_FIELDS = ("isin", "symbol", "name", "market", "yahoo_ticker", "kind", "currency")
USER_AGENT = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36 ({APP_NAME})"


def write_snapshot(path: Path, items: list[ListedSecurity]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SNAPSHOT_FIELDS)
        writer.writeheader()
        for item in sorted(items, key=lambda s: s.yahoo_ticker):
            writer.writerow({field: getattr(item, field) or "" for field in SNAPSHOT_FIELDS})


def read_snapshot(path: Path) -> list[ListedSecurity]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            ListedSecurity(isin=row["isin"] or None, symbol=row["symbol"], name=row["name"], market=row["market"],
                           yahoo_ticker=row["yahoo_ticker"], kind=row["kind"], currency=row["currency"] or None)
            for row in csv.DictReader(handle)
        ]


class SourceListing:
    source = ""
    min_rows = 1  # en dessous, le fichier est jugé tronqué : il désactiverait la plupart des titres

    def __init__(self, http_get: Callable[[str], str] | None = None, sleep: Callable[[float], None] = time.sleep,
                 snapshot_path: Path | None = None) -> None:
        self._http_get = http_get or self._default_get
        self._sleep = sleep
        self._snapshot_path = snapshot_path or SNAPSHOT_DIR / f"{self.source}.csv"

    def fetch_live(self) -> list[ListedSecurity]:
        raise NotImplementedError

    def fetch_listed(self) -> list[ListedSecurity]:
        try:
            listed = with_retries(self.fetch_live, sleep=self._sleep)
            if len(listed) < self.min_rows:
                raise ValueError(f"Liste {self.source} incomplète ({len(listed)} titres)")
            return listed
        except Exception:
            logger.warning("Liste %s indisponible, utilisation de l'instantané local", self.source, exc_info=True)
            listed = read_snapshot(self._snapshot_path)
            if not listed:
                raise ValueError(f"Instantané {self.source} vide")
            return listed

    def _get(self, url: str) -> str:
        return self._http_get(url)

    @staticmethod
    def _default_get(url: str) -> str:
        response = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}, timeout=60, follow_redirects=True)
        response.raise_for_status()
        return response.text
```

`providers/us.py`:

```python
"""Actions et ETF américains : fichier public `nasdaqtraded.txt` de Nasdaq Trader (NYSE, NYSE American, NYSE Arca, Nasdaq)."""
import csv
import re

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

NASDAQ_TRADED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
EXCHANGES = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca", "Q": "Nasdaq"}
_EXPECTED_HEADER = "Nasdaq Traded|Symbol|Security Name|Listing Exchange"
# Bons de souscription, droits, unités (SPAC) et actions préférentielles : hors périmètre.
_EXCLUDED_NAME = re.compile(r"\b(warrants?|rights?|units?|preferred)\b", re.IGNORECASE)
_EXCLUDED_SYMBOL = re.compile(r"[$^=+]")


def parse_nasdaq_traded(text: str) -> list[ListedSecurity]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or not lines[0].startswith(_EXPECTED_HEADER):
        raise ValueError("Format de fichier Nasdaq Trader inattendu")
    listed = []
    for row in csv.DictReader(lines, delimiter="|"):
        market = EXCHANGES.get(row.get("Listing Exchange") or "")
        symbol = (row.get("Symbol") or "").strip()
        name = (row.get("Security Name") or "").strip()
        if (row.get("Nasdaq Traded") != "Y" or row.get("Test Issue") != "N" or row.get("NextShares") == "Y"
                or market is None or not symbol or _EXCLUDED_SYMBOL.search(symbol) or _EXCLUDED_NAME.search(name)):
            continue
        kind = "etf" if row.get("ETF") == "Y" else "stock"
        listed.append(ListedSecurity(isin=None, symbol=symbol, name=name, market=market,
                                     yahoo_ticker=symbol.replace(".", "-"), kind=kind, currency="USD"))
    return listed


class UsListingProvider(SourceListing):
    source = "us"
    min_rows = 5000

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_nasdaq_traded(self._get(NASDAQ_TRADED_URL))
```

`providers/euronext.py` (append):

```python
EURONEXT_ETF_URL = ("https://live.euronext.com/en/pd_es/data/track/download"
                    "?mics=XPAR,XAMS,XBRU,XMIL,XLIS,XDUB,XOSL,ETFP")  # dm_all_track ne renvoie aucune ligne


class EuronextEtfListingProvider(SourceListing):
    source = "euronext_etf"
    min_rows = 1000

    def __init__(self, http_post: Callable[[str, dict[str, str]], str] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._http_post = http_post or EuronextListingProvider._default_post

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_euronext_csv(self._http_post(EURONEXT_ETF_URL, FORM_DATA), kind="etf")
```

(import `SourceListing` from `app.providers.listing_source`.)

- [ ] **Step 4: Run** the new file, `tests/test_euronext.py`, then the suite. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: Euronext ETF and US listing sources with snapshot fallback`

---

### Task 5: Listing sources — Xetra, SIX, Nasdaq Nordic, snapshots

**Files:**
- Create: `backend/app/providers/xetra.py`, `backend/app/providers/six.py`, `backend/app/providers/nordic.py`, `backend/app/seeds/snapshots.py`
- Create (generated): `backend/app/seeds/listings/{euronext_etf,us,xetra,six,nordic}.csv`
- Test: `backend/tests/test_listing_sources.py` (append)

**Interfaces:**
- Consumes: `SourceListing`, `write_snapshot` (Task 4).
- Produces:
  - `xetra.find_csv_url(html) -> str`, `xetra.parse_xetra_csv(text)`, `XetraListingProvider` (`source = "xetra"`, `min_rows = 1000`; keeps « Instrument Type » `CS` → stock, `ETF` → etf, active products only; ticker `{Mnemonic}.DE`; market `Xetra`)
  - `six.parse_six_shares(text)`, `six.parse_six_etfs(text)`, `SixListingProvider` (`source = "six"`, `min_rows = 500`; ticker `{symbol}.SW`; market `SIX Swiss Exchange`; ETFs = `SecTypeDesc == "Exchange Traded Fund"`)
  - `nordic.parse_nordic(text, market_code)`, `NordicListingProvider` (`source = "nordic"`, `min_rows = 300`; markets `STO`→`.ST`/« Nasdaq Stockholm », `HEL`→`.HE`/« Nasdaq Helsinki », `CPH`→`.CO`/« Nasdaq Copenhagen », `ICE`→`.IC`/« Nasdaq Iceland »; categories `MAIN_MARKET`, `FIRST_NORTH`; spaces in symbols → `-`)
  - `python -m app.seeds.snapshots [source…]`: fetches the live lists and rewrites their snapshots; exits 1 if a source fails.

- [ ] **Step 1: Failing tests** (append to `test_listing_sources.py`):

```python
from app.providers.nordic import NordicListingProvider, parse_nordic
from app.providers.six import parse_six_etfs, parse_six_shares
from app.providers.xetra import XetraListingProvider, find_csv_url, parse_xetra_csv

XETRA_CSV = (
    "Market:;XETR\nDate Last Update:;02.10.2026\n"
    "Product Status;Instrument Status;Instrument;ISIN;Product ID;Instrument ID;WKN;Mnemonic;Instrument Type;Currency\n"
    "Active;Active;SAP SE O.N.;DE0007164600;1;2;716460;SAP;CS;EUR\n"
    "Active;Active;ISHS CORE MSCI WORLD;IE00B4L5Y983;3;4;A0RPWH;EUNL;ETF;EUR\n"
    "Active;Active;SOME ETN;DE000A0S9GB0;5;6;A0S9GB;4GLD;ETN;EUR\n"
    "Inactive;Active;OLD AG;DE0001234567;7;8;123456;OLD;CS;EUR\n"
)


def test_parse_xetra_keeps_active_stocks_and_etfs():
    listed = {s.yahoo_ticker: s for s in parse_xetra_csv(XETRA_CSV)}
    assert set(listed) == {"SAP.DE", "EUNL.DE"}
    assert (listed["SAP.DE"].kind, listed["SAP.DE"].market, listed["SAP.DE"].isin) == ("stock", "Xetra", "DE0007164600")
    assert listed["EUNL.DE"].kind == "etf"


def test_xetra_link_is_found_on_the_instruments_page():
    html = '<a href="https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/8d76/data/t7-xetr-allTradableInstruments.csv">CSV</a>'
    assert find_csv_url(html).endswith("t7-xetr-allTradableInstruments.csv")
    pages = {"page": html}

    def get(url):
        return XETRA_CSV if url.endswith(".csv") else pages["page"]

    provider = XetraListingProvider(http_get=get, sleep=lambda s: None)
    provider.min_rows = 1
    assert len(provider.fetch_listed()) == 2


SIX_SHARES = ("Company;ISIN;Symbol;Valor Number;Country;Traded Currency;Trading platform\n"
              "ABB Ltd;CH0012221716;ABBN;1222171;CH;CHF;XSWX\n"
              "3M Company;US88579Y1010;MMM;1405105;US;CHF;XSWX\n")
SIX_ETFS = ("ShortName;ValorSymbol;ISIN;TradingBaseCurrency;SecTypeDesc\n"
            "iShares Core S&P 500;CSSPX;IE00B5BMR087;USD;Exchange Traded Fund\n"
            "Some Fund;SFUND;CH0000000001;CHF;Sponsored Funds\n")


def test_parse_six():
    shares = {s.yahoo_ticker: s for s in parse_six_shares(SIX_SHARES)}
    assert (shares["ABBN.SW"].currency, shares["ABBN.SW"].market) == ("CHF", "SIX Swiss Exchange")
    assert "MMM.SW" in shares  # l'élimination des cotations secondaires se fait à la fusion (tâche 6)
    etfs = parse_six_etfs(SIX_ETFS)
    assert [(e.yahoo_ticker, e.kind, e.currency) for e in etfs] == [("CSSPX.SW", "etf", "USD")]


NORDIC_JSON = ('{"data":{"instrumentListing":{"rows":['
               '{"fullName":"AAK","currency":"SEK","symbol":"AAK","isin":"SE0011337708","assetClass":"SHARES"},'
               '{"fullName":"Acrinova A","currency":"SEK","symbol":"ACRI A","isin":"SE0000000001","assetClass":"SHARES"}]}}}')


def test_parse_nordic():
    listed = parse_nordic(NORDIC_JSON, "STO")
    assert [(s.yahoo_ticker, s.market, s.currency) for s in listed] == [
        ("AAK.ST", "Nasdaq Stockholm", "SEK"), ("ACRI-A.ST", "Nasdaq Stockholm", "SEK")]


def test_nordic_provider_reads_every_market_and_category():
    urls = []

    def get(url):
        urls.append(url)
        return NORDIC_JSON

    provider = NordicListingProvider(http_get=get, sleep=lambda s: None)
    provider.min_rows = 1
    provider.fetch_listed()
    assert len(urls) == 8 and any("market=ICE" in u and "FIRST_NORTH" in u for u in urls)
```

- [ ] **Step 2: Run** the file. Expected: FAIL at import.

- [ ] **Step 3: Implement**

`providers/xetra.py`:

```python
"""Xetra : fichier « All tradable instruments » de Deutsche Börse (lien à empreinte, lu sur la page des instruments)."""
import csv
import re

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

INSTRUMENTS_PAGE = "https://www.xetra.com/xetra-en/instruments/instruments"
_CSV_LINK = re.compile(r'href="([^"]*t7-xetr-allTradableInstruments\.csv)"')
_KINDS = {"CS": "stock", "ETF": "etf"}
_PREAMBLE_LINES = 2


def find_csv_url(html: str) -> str:
    match = _CSV_LINK.search(html)
    if match is None:
        raise ValueError("Lien du fichier Xetra introuvable")
    url = match.group(1)
    return url if url.startswith("http") else f"https://www.xetra.com{url}"


def parse_xetra_csv(text: str) -> list[ListedSecurity]:
    lines = text.lstrip("﻿").splitlines()
    if len(lines) <= _PREAMBLE_LINES or "Mnemonic" not in lines[_PREAMBLE_LINES]:
        raise ValueError("Format de fichier Xetra inattendu")
    listed = []
    for row in csv.DictReader(lines[_PREAMBLE_LINES:], delimiter=";"):
        kind = _KINDS.get(row.get("Instrument Type") or "")
        mnemonic = (row.get("Mnemonic") or "").strip()
        if kind is None or row.get("Product Status") != "Active" or not mnemonic:
            continue
        listed.append(ListedSecurity(isin=(row.get("ISIN") or "").strip() or None, symbol=mnemonic,
                                     name=(row.get("Instrument") or "").strip(), market="Xetra",
                                     yahoo_ticker=f"{mnemonic}.DE", kind=kind,
                                     currency=(row.get("Currency") or "").strip() or None))
    return listed


class XetraListingProvider(SourceListing):
    source = "xetra"
    min_rows = 1000

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_xetra_csv(self._get(find_csv_url(self._get(INSTRUMENTS_PAGE))))
```

If Step 4 against the live file shows the header has several `Currency` columns, `DictReader` keeps the last one: switch to the first index found in the header line and ledger a ruling.

`providers/six.py`:

```python
"""SIX Swiss Exchange : émetteurs d'actions cotées et ETF (fichiers CSV publics)."""
import csv

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

SHARES_URL = "https://www.six-group.com/sheldon/equity_issuers/v1/equity_issuers.csv"
ETFS_URL = ("https://www.six-group.com/fqs/ref.csv?select=ShortName,ValorSymbol,ISIN,TradingBaseCurrency,SecTypeDesc"
            "&where=PortalSegment=FU&orderby=ShortName&page=1&pagesize=99999")
MARKET = "SIX Swiss Exchange"


def _rows(text: str, first_column: str) -> list[dict[str, str]]:
    lines = text.lstrip("﻿").splitlines()
    if not lines or not lines[0].startswith(first_column):
        raise ValueError("Format de fichier SIX inattendu")
    return list(csv.DictReader(lines, delimiter=";"))


def _listed(symbol: str, name: str, isin: str, currency: str, kind: str) -> ListedSecurity:
    return ListedSecurity(isin=isin.strip() or None, symbol=symbol.strip(), name=name.strip(), market=MARKET,
                          yahoo_ticker=f"{symbol.strip()}.SW", kind=kind, currency=currency.strip() or None)


def parse_six_shares(text: str) -> list[ListedSecurity]:
    return [_listed(r["Symbol"], r["Company"], r["ISIN"], r.get("Traded Currency") or "", "stock")
            for r in _rows(text, "Company;") if r.get("Symbol")]


def parse_six_etfs(text: str) -> list[ListedSecurity]:
    return [_listed(r["ValorSymbol"], r["ShortName"], r["ISIN"], r.get("TradingBaseCurrency") or "", "etf")
            for r in _rows(text, "ShortName;") if r.get("ValorSymbol") and r.get("SecTypeDesc") == "Exchange Traded Fund"]


class SixListingProvider(SourceListing):
    source = "six"
    min_rows = 500

    def fetch_live(self) -> list[ListedSecurity]:
        return parse_six_shares(self._get(SHARES_URL)) + parse_six_etfs(self._get(ETFS_URL))
```

`providers/nordic.py`:

```python
"""Nasdaq Nordic (Stockholm, Helsinki, Copenhague, Islande) : écran des actions de l'API publique de nasdaq.com."""
import json

from app.providers.base import ListedSecurity
from app.providers.listing_source import SourceListing

SCREENER_URL = "https://api.nasdaq.com/api/nordic/screener/shares?category={category}&tableonly=false&market={market}"
MARKETS = {"STO": (".ST", "Nasdaq Stockholm"), "HEL": (".HE", "Nasdaq Helsinki"),
           "CPH": (".CO", "Nasdaq Copenhagen"), "ICE": (".IC", "Nasdaq Iceland")}
CATEGORIES = ("MAIN_MARKET", "FIRST_NORTH")


def parse_nordic(text: str, market_code: str) -> list[ListedSecurity]:
    suffix, market = MARKETS[market_code]
    rows = ((json.loads(text).get("data") or {}).get("instrumentListing") or {}).get("rows")
    if rows is None:
        raise ValueError("Format de réponse Nasdaq Nordic inattendu")
    listed = []
    for row in rows:
        symbol = (row.get("symbol") or "").strip()
        if not symbol:
            continue
        listed.append(ListedSecurity(isin=(row.get("isin") or "").strip() or None, symbol=symbol,
                                     name=(row.get("fullName") or symbol).strip(), market=market,
                                     yahoo_ticker=f"{symbol.replace(' ', '-')}{suffix}", kind="stock",
                                     currency=(row.get("currency") or "").strip() or None))
    return listed


class NordicListingProvider(SourceListing):
    source = "nordic"
    min_rows = 300

    def fetch_live(self) -> list[ListedSecurity]:
        return [item for market in MARKETS for category in CATEGORIES
                for item in parse_nordic(self._get(SCREENER_URL.format(category=category, market=market)), market)]
```

`seeds/snapshots.py`:

```python
"""Rafraîchit les instantanés des listes de titres (repli quand une source est en panne).

Usage : python -m app.seeds.snapshots [euronext_etf us xetra six nordic]
"""
import sys

from app.providers.euronext import EuronextEtfListingProvider
from app.providers.listing_source import SNAPSHOT_DIR, write_snapshot
from app.providers.nordic import NordicListingProvider
from app.providers.six import SixListingProvider
from app.providers.us import UsListingProvider
from app.providers.xetra import XetraListingProvider

PROVIDERS = {p.source: p for p in (EuronextEtfListingProvider, UsListingProvider, XetraListingProvider,
                                   SixListingProvider, NordicListingProvider)}


def main(names: list[str]) -> int:
    failed = 0
    for name in names or list(PROVIDERS):
        provider = PROVIDERS[name]()
        try:
            listed = provider.fetch_live()  # jamais l'instantané : on le remplace
            if len(listed) < provider.min_rows:
                raise ValueError(f"{len(listed)} titres seulement")
        except Exception as exc:
            print(f"ÉCHEC {name} : {exc}")
            failed += 1
            continue
        write_snapshot(SNAPSHOT_DIR / f"{name}.csv", listed)
        print(f"{name} : {len(listed)} titres")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run** the test file and the suite (PASS). Then generate the snapshots live (the `api` image mounts `backend/` in dev):

Run: `docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm -T api python -m app.seeds.snapshots`
Expected: five lines `<source> : N titres` with N ≥ each `min_rows` (≈ 3,000 / 9,500 / 4,500 / 2,500 / 1,000), exit 0. Check sizes with `ls -la backend/app/seeds/listings` (expect a few hundred KB each) and spot-check two rows per file. Any source that fails here: fix its parser against the live format (ledger the ruling), never commit a partial snapshot.

- [ ] **Step 5: Commit** — `feat: Xetra, SIX and Nasdaq Nordic listing sources, versioned snapshots`

---

### Task 6: Universe merge, per-source deactivation, ETF rule

**Files:**
- Modify: `backend/app/jobs/universe.py`, `backend/app/repositories/securities.py` (`SecurityUpsert`, `upsert_securities`, `deactivate_missing`), `backend/app/jobs/context.py` (`listings`), `backend/app/jobs/worker.py`, `backend/tests/conftest.py` (`make_ctx`), `backend/tests/fakes.py` (`FakeListing.source`)
- Modify: `backend/app/services/envelopes/rules.py` (ETF rule + docstring), `backend/app/repositories/envelopes.py` (`facts_for`), `backend/app/seeds/loader.py` (`confirmed_pea_etfs`)
- Test: `backend/tests/test_universe.py`, `backend/tests/test_envelope_rules.py` (or the file that tests `pea_status`; find it with `grep -rln pea_status backend/tests`)

**Interfaces:**
- Consumes: every provider of Tasks 2, 4, 5.
- Produces:
  - `JobContext.listings: Sequence[ListingProvider]` (replaces `listing`); `make_ctx(listing=…)` still accepted and wrapped in a list; `make_ctx(listings=[…])` new
  - `universe.SOURCE_PRIORITY = ("euronext", "euronext_etf", "nordic", "six", "xetra", "us")`, `universe.HOME_COUNTRIES`, `universe.merge_listings(batches: dict[str, list[ListedSecurity]]) -> list[tuple[str, ListedSecurity]]`
  - `SecurityUpsert(..., currency: str | None = None, source: str | None = None)`
  - `deactivate_missing(session, seen_tickers, sources: set[str] | None = None)`
  - `SecurityFacts(..., name: str = "", confirmed_etf: bool = False)`; `loader.confirmed_pea_etfs() -> frozenset[str]`

- [ ] **Step 1: Failing tests**

Append to `test_universe.py`:

```python
SAP_XETRA = ListedSecurity("DE0007164600", "SAP", "SAP SE", "Xetra", "SAP.DE", "stock", "EUR")
SAP_SIX = ListedSecurity("DE0007164600", "SAP", "SAP SE", "SIX Swiss Exchange", "SAP.SW", "stock", "CHF")
APPLE_XETRA = ListedSecurity("US0378331005", "APC", "Apple Inc.", "Xetra", "APC.DE", "stock", "EUR")
APPLE_US = ListedSecurity(None, "AAPL", "Apple Inc.", "Nasdaq", "AAPL", "stock", "USD")
STRABAG_XETRA = ListedSecurity("AT000000STR1", "XD4", "STRABAG SE", "Xetra", "XD4.DE", "stock", "EUR")
WORLD_PARIS = ListedSecurity("IE00B4L5Y983", "IWDA", "iShares Core MSCI World", "Euronext Amsterdam", "IWDA.AS", "etf", "EUR")
WORLD_XETRA = ListedSecurity("IE00B4L5Y983", "EUNL", "iShares Core MSCI World", "Xetra", "EUNL.DE", "etf", "EUR")
PEA_ETF = ListedSecurity("FR0011869312", "PAEJ", "AM ASIP EXJ PEA", "Euronext Paris", "PAEJ.PA", "etf", "EUR")


def test_merge_prefers_home_listing():
    merged = merge_listings({"six": [SAP_SIX], "xetra": [SAP_XETRA]})
    assert [(source, s.yahoo_ticker) for source, s in merged] == [("xetra", "SAP.DE")]


def test_merge_drops_secondary_listing_of_covered_country():
    merged = {s.yahoo_ticker for _, s in merge_listings({"xetra": [APPLE_XETRA, STRABAG_XETRA], "us": [APPLE_US]})}
    assert merged == {"AAPL", "XD4.DE"}  # Vienne n'est pas suivie : Strabag reste via Xetra


def test_merge_keeps_one_etf_per_isin_by_source_priority():
    merged = merge_listings({"xetra": [WORLD_XETRA], "euronext_etf": [WORLD_PARIS]})
    assert [s.yahoo_ticker for _, s in merged] == ["IWDA.AS"]


def test_universe_reads_every_source(db, make_ctx):
    refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([APPLE_US], source="us"),
                                        FakeListing([PEA_ETF, WORLD_PARIS], source="euronext_etf")]))
    apple = by_ticker(db, "AAPL")
    assert (apple.source, apple.currency, apple.envelope_status("pea")) == ("us", "USD", "non_eligible")
    assert by_ticker(db, "MC.PA").source == "euronext"
    assert (by_ticker(db, "PAEJ.PA").envelope_status("pea"), by_ticker(db, "PAEJ.PA").envelope("pea").source) == ("eligible", "auto")
    assert by_ticker(db, "IWDA.AS").envelope_status("pea") == "a_verifier"


def test_failed_source_keeps_its_securities(db, make_ctx):
    refresh_universe(make_ctx(listings=[FakeListing([LVMH, ASML]), FakeListing([APPLE_US], source="us")]))
    with pytest.raises(RuntimeError, match="us"):
        refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([], source="us")]))
    assert by_ticker(db, "AAPL").active is True
    assert by_ticker(db, "ASML.AS").active is False  # Euronext a répondu : ASML a bien disparu


def test_confirmed_seed_etf_from_a_source_stays_eligible(db, make_ctx):
    cw8 = ListedSecurity("LU1681043599", "CW8", "AMUNDI MSCI WORLD SWAP", "Euronext Paris", "CW8.PA", "etf", "EUR")
    refresh_universe(make_ctx(listings=[FakeListing([LVMH]), FakeListing([cw8], source="euronext_etf")]))
    security = by_ticker(db, "CW8.PA")
    assert (security.source, security.isin) == ("euronext_etf", "LU1681043599")
    assert (security.envelope_status("pea"), security.envelope("pea").source) == ("eligible", "seed")
```

(import `pytest` at module top and `merge_listings` from `app.jobs.universe`; check `CW8.PA` is in `seeds/etfs.csv`.)

Rules tests (in the file that tests `pea_status`):

```python
def test_etf_eligibility_needs_confirmation_or_pea_in_name():
    assert pea_status(SecurityFacts("etf", None, None, name="iShares Core MSCI World", confirmed_etf=True)) == (ELIGIBLE, "seed")
    assert pea_status(SecurityFacts("etf", None, None, name="AM ASIP EXJ PEA")) == (ELIGIBLE, "auto")
    assert pea_status(SecurityFacts("etf", "IE", None, name="iShares Core MSCI World")) == (TO_CHECK, "auto")
    assert pea_status(SecurityFacts("etf", None, None, name="Speaker Corp")) == (TO_CHECK, "auto")  # « PEA » doit être un mot
```

- [ ] **Step 2: Run** `tests/test_universe.py` and the rules test file. Expected: FAIL (`merge_listings` missing, `listings` unexpected, etc.).

- [ ] **Step 3: Implement**

`jobs/universe.py`:

```python
import logging

from app.jobs.context import JobContext
from app.providers.base import ListedSecurity
from app.repositories.securities import SecurityUpsert, deactivate_missing, upsert_securities
from app.seeds.loader import load_all_seeds
from app.services.envelopes.rules import country_from_isin

logger = logging.getLogger(__name__)

# Un même ISIN coté sur plusieurs places : la place d'origine d'abord, puis cet ordre (Euronext avant tout pour le PEA).
SOURCE_PRIORITY = ("euronext", "euronext_etf", "nordic", "six", "xetra", "us")
HOME_COUNTRIES: dict[str, frozenset[str]] = {
    "euronext": frozenset({"FR", "NL", "BE", "IT", "PT", "IE", "NO"}),
    "euronext_etf": frozenset(),
    "nordic": frozenset({"SE", "FI", "DK", "IS"}),
    "six": frozenset({"CH", "LI"}),
    "xetra": frozenset({"DE"}),
    "us": frozenset({"US"}),
}
COVERED_COUNTRIES = frozenset().union(*HOME_COUNTRIES.values())


def merge_listings(batches: dict[str, list[ListedSecurity]]) -> list[tuple[str, ListedSecurity]]:
    """Une cotation par ISIN et par ticker. Une action cotée hors de chez elle n'est gardée que si sa place n'est pas suivie."""
    candidates = []
    for rank, source in enumerate(SOURCE_PRIORITY):
        home = HOME_COUNTRIES[source]
        for item in batches.get(source, []):
            country = country_from_isin(item.isin)
            if source != "euronext" and item.kind == "stock" and country in COVERED_COUNTRIES and country not in home:
                continue  # cotation secondaire (Apple à Francfort) : la place d'origine est déjà suivie
            candidates.append((country not in home, rank, source, item))
    candidates.sort(key=lambda c: (c[0], c[1]))
    seen_isins: set[str] = set()
    seen_tickers: set[str] = set()
    merged = []
    for _, _, source, item in candidates:
        if (item.isin and item.isin in seen_isins) or item.yahoo_ticker in seen_tickers:
            continue
        if item.isin:
            seen_isins.add(item.isin)
        seen_tickers.add(item.yahoo_ticker)
        merged.append((source, item))
    return merged


def refresh_universe(ctx: JobContext) -> int:
    batches: dict[str, list[ListedSecurity]] = {}
    failed: list[str] = []
    for provider in ctx.listings:
        try:
            listed = provider.fetch_listed()
        except Exception:
            logger.warning("Liste %s indisponible (instantané compris)", provider.source, exc_info=True)
            listed = []
        if listed:
            batches[provider.source] = listed
        else:
            failed.append(provider.source)
    if not batches:
        raise RuntimeError("Aucune liste de titres disponible : univers conservé tel quel")
    items = [
        SecurityUpsert(yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind=s.kind, market=s.market,
                       isin=s.isin, country=country_from_isin(s.isin), currency=s.currency, source=source)
        for source, s in merge_listings(batches)
    ]
    listed_tickers = {item.yahoo_ticker for item in items}
    items += [
        SecurityUpsert(yahoo_ticker=s.yahoo_ticker, symbol=s.symbol, name=s.name, kind=s.kind, market=s.market,
                       isin=None, country=s.country, source="seed")
        for s in load_all_seeds() if s.yahoo_ticker not in listed_tickers  # une source prime sur la saisie manuelle
    ]
    with ctx.session_factory() as session:
        count = upsert_securities(session, items)
        deactivate_missing(session, {item.yahoo_ticker for item in items}, sources=set(batches) | {"seed"})
        session.commit()
    if failed:
        raise RuntimeError(f"Listes indisponibles ({', '.join(failed)}) : leurs titres sont conservés")
    return count
```

`repositories/securities.py`: add `currency: str | None = None` and `source: str | None = None` to `SecurityUpsert`; in `upsert_securities` set `security.currency = item.currency` and `security.source = item.source`; `deactivate_missing(..., sources: set[str] | None = None)` adds `.where(Security.source.in_(sources))` when given.

`jobs/context.py`: `listings: Sequence[ListingProvider]` (import `Sequence` from `collections.abc`).

`tests/fakes.py`: `FakeListing.__init__(self, items=None, source: str = "euronext")` storing `self.source`.

`tests/conftest.py` `make_ctx`: signature `_make(market=None, listing=None, listings=None, now=None, mailer=None, billing=None, **settings_overrides)` and `listings=listings or [listing or FakeListing()]`. Update any test that reads `ctx.listing` (grep).

`jobs/worker.py`:

```python
        listings=[
            EuronextListingProvider(settings.euronext_list_url), EuronextEtfListingProvider(), NordicListingProvider(),
            SixListingProvider(), XetraListingProvider(), UsListingProvider(),
        ],
```

`seeds/loader.py`:

```python
@lru_cache
def confirmed_pea_etfs() -> frozenset[str]:
    """ETF dont l'éligibilité au PEA est confirmée à la main (seeds/etfs.csv)."""
    return frozenset(row["yahoo_ticker"] for row in _read("etfs.csv"))
```

`services/envelopes/rules.py`: add `name: str = ""` and `confirmed_etf: bool = False` to `SecurityFacts`; module constant `_PEA_IN_NAME = re.compile(r"\bPEA\b")`; ETF branch of `pea_status`:

```python
    if facts.kind == "etf":
        if facts.confirmed_etf:
            return ELIGIBLE, "seed"
        # Jamais déduit du pays de l'émetteur : un ETF UCITS irlandais n'est pas éligible par défaut.
        return (ELIGIBLE, "auto") if _PEA_IN_NAME.search(facts.name) else (TO_CHECK, "auto")
```

Docstring: replace « ETF et indices : listes de départ (`seeds/`). » with « Indices : jamais éligibles. ETF : éligibles s'ils sont confirmés (`seeds/etfs.csv`) ou si leur nom contient le mot « PEA », sinon « à vérifier ». »

`repositories/envelopes.py` `facts_for`: pass `name=security.name` and `confirmed_etf=security.kind == "etf" and security.yahoo_ticker in confirmed_pea_etfs()`.

- [ ] **Step 4: Run** `tests/test_universe.py`, the rules tests, then the full suite. Expected: PASS. Existing `test_universe_classifies_listed_and_seeds` still passes (seed ETFs are confirmed).

- [ ] **Step 5: Commit** — `feat: multi-source universe with home-place dedup and ETF PEA rule`

---

### Task 7: Jobs by place — tiers, US evening pass, closing quotes, intraday scores

**Files:**
- Modify: `backend/app/jobs/tiers.py`, `backend/app/jobs/market.py` (`refresh_quotes`, `refresh_daily_history(region)`, `_write_closing_quotes`), `backend/app/jobs/scheduler.py` (`quotes_job`, `evening_job`, new `us_evening_job`, cron), `backend/app/jobs/notifications.py` (`run_price_moves`), `backend/app/jobs/scoring.py` (`refresh_scores(open_only)`), `backend/app/repositories/market_data.py` (`daily_series(security_ids)`)
- Test: `backend/tests/test_tiers.py` (or the file testing `tier_tickers`), `backend/tests/test_market_jobs.py`, `backend/tests/test_scheduler.py`, `backend/tests/test_scoring_job.py` (find the file testing `refresh_scores`)

**Interfaces:**
- Consumes: `calendar_for_market`, `any_market_open`, `EUROPE`, `US` (Task 1); `run_job(ctx, "fx", refresh_fx)` (Task 3).
- Produces:
  - `tier_tickers(session, tier, tier2_size, now: datetime | None = None)` — with `now`, only securities whose place is open (indices follow Europe)
  - `refresh_daily_history(ctx, region: str | None = None)` — `"europe"` / `"us"` / all
  - `refresh_scores(ctx, open_only: bool = False)`
  - `daily_series(session, since, security_ids: Collection[int] | None = None)`
  - `us_evening_job(ctx)`, cron id `"us_evening"` mon-fri 22:30

- [ ] **Step 1: Failing tests**

```python
# tiers
def test_tiers_only_fetch_open_places(db):
    make_security(db, "MC.PA", market="Euronext Paris")
    make_security(db, "AAPL", market="Nasdaq")
    evening = datetime(2026, 10, 2, 19, 0, tzinfo=PARIS)  # Europe fermée, New York ouverte
    tickers = tier_tickers(db, 2, 150, evening) + tier_tickers(db, 3, 150, evening)
    assert tickers == ["AAPL"]
    afternoon = datetime(2026, 10, 2, 16, 0, tzinfo=PARIS)
    assert set(tier_tickers(db, 2, 150, afternoon) + tier_tickers(db, 3, 150, afternoon)) == {"MC.PA", "AAPL"}


# scheduler
def test_quotes_job_runs_while_only_new_york_is_open(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "_refresh_tier", lambda ctx, tier: calls.append(tier))
    monkeypatch.setattr(scheduler, "_refresh_scores", lambda ctx, **kw: None)
    scheduler.quotes_job(make_ctx(now=datetime(2026, 10, 2, 19, 0, tzinfo=PARIS)), 2)
    assert calls == [2]


def test_us_evening_job_is_scheduled_at_22_30(make_ctx):
    job = build_scheduler(make_ctx(), BackgroundScheduler()).get_job("us_evening")
    assert str(job.trigger.fields[job.trigger.FIELD_NAMES.index("hour")]) == "22"
    assert str(job.trigger.fields[job.trigger.FIELD_NAMES.index("minute")]) == "30"


# market jobs
def test_daily_history_by_region(db, make_ctx):
    paris = make_security(db, "MC.PA", market="Euronext Paris")
    ny = make_security(db, "AAPL", market="Nasdaq")
    for s in (paris, ny):
        store(db, s, date(2026, 10, 1), 10.0)
    market = FakeMarket(history={"MC.PA": [bar(date(2026, 10, 2), 11.0)], "AAPL": [bar(date(2026, 10, 2), 12.0)]})
    refresh_daily_history(make_ctx(market=market), region="us")
    assert [tickers for tickers, _ in market.history_calls] == [["AAPL"]]


def test_closing_quote_uses_the_place_close_time(db, make_ctx):
    ny = make_security(db, "AAPL", market="Nasdaq")
    store(db, ny, date(2026, 10, 1), 10.0)
    refresh_daily_history(make_ctx(market=FakeMarket(history={"AAPL": [bar(date(2026, 10, 1), 10.0), bar(date(2026, 10, 2), 12.0)]})))
    quote = db.get(SecurityQuote, ny.id)
    assert quote.as_of == datetime(2026, 10, 2, 22, 0, tzinfo=PARIS)


# scoring
def test_intraday_scores_only_touch_open_places(db, make_ctx):
    # deux titres avec un score existant ; à 19 h seule l'action américaine est recalculée
    ...
```

Write the scoring test fully in the existing scoring test file's style: seed two securities with ~250 daily bars each (reuse its helper), run `refresh_scores(ctx)` at 16:00 Paris, record both `computed_at`, then `refresh_scores(ctx_at_19h, open_only=True)` and assert only the Nasdaq one changed `computed_at` and the Paris one kept `eligible_for_top`. Reuse `store`/`bar` helpers where the files already have them (`test_history_backfill.py` has both); otherwise copy them.

- [ ] **Step 2: Run** the touched test files. Expected: FAIL.

- [ ] **Step 3: Implement**

`jobs/tiers.py`:

```python
def tier_tickers(session: Session, tier: int, tier2_size: int, now: datetime | None = None) -> list[str]:
    """… (docstring actuelle) Avec `now`, seuls les titres dont la place est ouverte (les indices suivent l'Europe)."""
    candidates = refreshable_securities(session)
    if now is not None:
        candidates = [s for s in candidates if calendar_for_market(s.market).is_open(now)]
    # (suite inchangée)
```

`jobs/market.py`:
- `refresh_quotes`: `tier_tickers(session, tier, ctx.settings.tier2_size, ctx.now())`.
- `refresh_daily_history(ctx, region: str | None = None)`: skip securities with `region is not None and calendar_for_market(security.market).code != region`.
- `_write_closing_quotes`: load `{id: market}` for the ids (`select(Security.id, Security.market).where(Security.id.in_(security_ids))`) and use `as_of=calendar_for_market(markets[security_id]).session_close(last.date)`; drop the `CLOSE` import.

`jobs/scheduler.py`:

```python
def quotes_job(ctx: JobContext, tier: int) -> None:
    if any_market_open(ctx.now()):
        _refresh_tier(ctx, tier)
        _quietly(ctx, run_price_alerts)  # N2 : après chaque mise à jour des cours
        if tier == 2:
            _refresh_scores(ctx, open_only=True)  # les places fermées n'ont pas bougé


def _refresh_scores(ctx: JobContext, open_only: bool = False) -> None:
    run_job(ctx, "scores", lambda c: refresh_scores(c, open_only=open_only))


def evening_job(ctx):  # existing body, with region="europe" passed to refresh_daily_history
    ...


def us_evening_job(ctx: JobContext) -> None:
    """Après la clôture de New York : clôtures officielles des titres américains, puis scores et prévisions."""
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "fx", refresh_fx)
        run_job(ctx, "daily_history_us", lambda c: refresh_daily_history(c, region="us"))
        _refresh_scores(ctx)
        _refresh_forecasts(ctx)
```

`evening_job` uses `run_job(ctx, "daily_history", lambda c: refresh_daily_history(c, region="europe"))` (same job name so `bootstrap_job`'s freshness check keeps working). Cron: `scheduler.add_job(us_evening_job, CronTrigger(day_of_week="mon-fri", hour=22, minute=30, timezone=tz), args=[ctx], id="us_evening", **daily)`.

`jobs/notifications.py` `run_price_moves`: `any_market_open` instead of `is_market_open`.

`repositories/market_data.py`:

```python
def daily_series(session: Session, since: date, security_ids: Collection[int] | None = None) -> dict[int, list[Row]]:
    stmt = select(...).where(DailyPrice.date >= since)
    if security_ids is not None:
        stmt = stmt.where(DailyPrice.security_id.in_(security_ids))
    # (suite inchangée)
```

`jobs/scoring.py` `refresh_scores(ctx, open_only: bool = False)`: after building `securities`, when `open_only`: keep `s.yahoo_ticker == INDEX_TICKER or calendar_for_market(s.market).is_open(now)`, call `daily_series(session, since, [s.id for s in securities])`, and skip the final « sortis du périmètre » `update` (only a full pass may clear `eligible_for_top`).

Update tests that monkeypatch `_refresh_scores` with a one-argument lambda to accept `**kw`.

- [ ] **Step 4: Run** touched files, then the full suite. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: quotes, closes and intraday scores follow each place's session`

---

### Task 8: Background first load and weekly fundamentals

**Files:**
- Modify: `backend/app/jobs/market.py` (`refresh_daily_history`, `backfill_history`, `refresh_fundamentals`), `backend/app/jobs/scheduler.py` (`history_backfill_job`, `universe_job`), `backend/app/repositories/market_data.py` (`incomplete_history_securities` unchanged; new `fundamentals_due`)
- Test: `backend/tests/test_history_backfill.py`, `backend/tests/test_market_jobs.py`, `backend/tests/test_scheduler.py`

**Interfaces:**
- Produces:
  - `refresh_daily_history` no longer loads securities without prices (the backfill does, in batches)
  - `backfill_history(ctx, guard: Callable[[], AbstractContextManager] = nullcontext) -> int` — `guard()` wraps each batch (fetch + write)
  - dead rule: absent from Yahoo and (last price older than `DEAD_AFTER`, or no price and `created_at` older than `DEAD_AFTER`)
  - `history_backfill_job(ctx)`: non-blocking `BACKFILL_LOCK` (skip if already running), `guard=lambda: HEAVY_JOBS_LOCK`, then scores if it wrote rows
  - `universe_job` runs `history_backfill_job` after releasing the heavy lock
  - `FUNDAMENTALS_DAYS = 5`; `fundamentals_due(session, share: int) -> list[tuple[int, str]]` (stocks, never-fetched first then oldest `updated_at`, `ceil(count / share)` of them)

- [ ] **Step 1: Failing tests**

`test_history_backfill.py` (append):

```python
def test_backfill_takes_the_guard_per_batch(db, make_ctx, monkeypatch):
    monkeypatch.setattr(market_module, "BACKFILL_BATCH", 1)
    make_security(db, "A.PA")
    make_security(db, "B.PA")
    entered = []

    @contextmanager
    def guard():
        entered.append(1)
        yield

    history = {"A.PA": [bar(date(2000, 1, 3), 1.0)], "B.PA": [bar(date(2000, 1, 3), 2.0)]}
    backfill_history(make_ctx(market=FakeMarket(history=history)), guard=guard)
    assert len(entered) == 2


def test_backfill_loads_new_securities_entirely(db, make_ctx):
    new = make_security(db, "NEW.PA")
    backfill_history(make_ctx(market=FakeMarket(history={"NEW.PA": [bar(date(2000, 1, 3), 1.0), bar(date(2026, 10, 1), 2.0)]})))
    assert closes(db, new) == [(date(2000, 1, 3), 1.0), (date(2026, 10, 1), 2.0)]
    assert complete(db, new) is True


def test_backfill_gives_up_on_unknown_tickers_after_a_month(db, make_ctx):
    unknown = make_security(db, "RAW.DE")
    unknown.created_at = datetime(2026, 8, 1, tzinfo=UTC)
    recent = make_security(db, "LATE.DE")
    recent.created_at = datetime(2026, 9, 25, tzinfo=UTC)
    db.flush()
    backfill_history(make_ctx(market=FakeMarket(), now=datetime(2026, 9, 28, 20, 0, tzinfo=UTC)))
    assert complete(db, unknown) is True
    assert complete(db, recent) is False
```

(`from contextlib import contextmanager`.)

`test_market_jobs.py`: change the existing test that expects a security without prices to be loaded with `None` into `test_daily_history_leaves_new_securities_to_the_backfill` — the security without prices is absent from `market.history_calls` and gets no rows.

`test_scheduler.py`:

```python
def test_backfill_job_skips_when_already_running(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "backfill_history", lambda ctx, guard: calls.append(1) or 0)
    assert scheduler.BACKFILL_LOCK.acquire(blocking=False)
    try:
        scheduler.history_backfill_job(make_ctx())
    finally:
        scheduler.BACKFILL_LOCK.release()
    assert calls == []


def test_backfill_job_does_not_hold_the_heavy_lock_between_batches(make_ctx, monkeypatch):
    seen = []

    def fake_backfill(ctx, guard):
        seen.append(scheduler.HEAVY_JOBS_LOCK.locked())
        with guard():
            seen.append(scheduler.HEAVY_JOBS_LOCK.locked())
        return 0

    monkeypatch.setattr(scheduler, "backfill_history", fake_backfill)
    scheduler.history_backfill_job(make_ctx())
    assert seen == [False, True]


def test_universe_job_then_backfills(make_ctx, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "run_job", lambda ctx, name, fn: calls.append(name) or 0)
    monkeypatch.setattr(scheduler, "history_backfill_job", lambda ctx: calls.append("backfill"))
    scheduler.universe_job(make_ctx())
    assert calls == ["universe", "backfill"]
```

Fundamentals (in `test_market_jobs.py`):

```python
def test_fundamentals_are_spread_over_the_week(db, make_ctx):
    stocks = [make_security(db, f"S{i}.PA") for i in range(10)]
    for i, s in enumerate(stocks[:8]):
        db.add(SecurityFundamentals(security_id=s.id, updated_at=datetime(2026, 9, 20 + i, tzinfo=UTC)))
    db.flush()
    market = FakeMarket()
    refresh_fundamentals(make_ctx(market=market))
    # 10 actions / 5 jours = 2 : les deux jamais chargées passent en premier
    assert market.fundamentals_calls == ["S8.PA", "S9.PA"]
```

Check `FakeMarket` for how it records fundamentals calls (attribute name) and `SecurityFundamentals` required columns; adapt names, keep the assertion.

- [ ] **Step 2: Run** the three files. Expected: FAIL.

- [ ] **Step 3: Implement**

`jobs/market.py`:
- `refresh_daily_history`: replace `by_start[last_dates.get(security.id)].append(...)` with `if security.id in last_dates: by_start[last_dates[security.id]].append(...)` (comment: « Titres sans aucun cours : chargés en entier par le rattrapage, par paquets »). Remove the `start is None` branches of the first loop; keep the readjusted reload as is.
- `backfill_history(ctx, guard=nullcontext)`: load `created = {s.id: s.created_at for s in incomplete}` with the targets; wrap the body of each batch iteration (from `get_daily_history` to `session.commit()`) in `with guard():`; dead rule:

```python
            cutoff = today - DEAD_AFTER
            done += [security_id for ticker, security_id in batch.items() if ticker not in history and (
                last_dates[security_id] < cutoff if security_id in last_dates
                else created[security_id].astimezone(PARIS).date() < cutoff)]
```

- `refresh_fundamentals`:

```python
FUNDAMENTALS_DAYS = 5  # chaque action est relue une fois par semaine (jours ouvrés)


def refresh_fundamentals(ctx: JobContext) -> int:
    with ctx.session_factory() as session:
        targets = fundamentals_due(session, FUNDAMENTALS_DAYS)
    # (boucle inchangée)
```

`repositories/market_data.py`:

```python
def fundamentals_due(session: Session, share: int) -> list[tuple[int, str]]:
    """La part du jour des actions actives : jamais chargées d'abord, puis les plus anciennes."""
    rows = session.execute(
        select(Security.id, Security.yahoo_ticker)
        .outerjoin(SecurityFundamentals, SecurityFundamentals.security_id == Security.id)
        .where(Security.active.is_(True), Security.kind == "stock")
        .order_by(SecurityFundamentals.updated_at.asc().nulls_first(), Security.id)
    ).all()
    return [(sid, ticker) for sid, ticker in rows[:math.ceil(len(rows) / share)]]
```

`jobs/scheduler.py`:

```python
# Le rattrapage dure des heures au premier chargement : un seul à la fois, verrou lourd repris à chaque paquet.
BACKFILL_LOCK = threading.Lock()


def history_backfill_job(ctx: JobContext) -> None:
    """Historique complet des titres sans historique : ne fait plus rien une fois tous les titres rattrapés."""
    if not BACKFILL_LOCK.acquire(blocking=False):
        return
    try:
        written = run_job(ctx, "history_backfill", lambda c: backfill_history(c, guard=lambda: HEAVY_JOBS_LOCK))
    finally:
        BACKFILL_LOCK.release()
    if written:
        _refresh_scores(ctx)  # les nouveaux titres ont maintenant de quoi être notés


def universe_job(ctx: JobContext) -> None:
    with HEAVY_JOBS_LOCK:
        run_job(ctx, "universe", refresh_universe)
    history_backfill_job(ctx)  # nouveaux titres : cours chargés en arrière-plan, paquet par paquet
```

Existing bootstrap tests that listed the order `[..., "scores", "history_backfill"]` keep passing only if the backfill wrote nothing in them; adjust their expectation if the fake history writes rows (ledger as a ruling, keep the intent « backfill last »).

- [ ] **Step 4: Run** the three files, then the full suite. Expected: PASS.

- [ ] **Step 5: Commit** — `feat: batched background first load and weekly fundamentals rotation`

---

### Task 9: Lists — hide unpriced securities, Explorer by region, market status per place

**Files:**
- Modify: `backend/app/repositories/screener.py` (`region`, priced only), `backend/app/api/routes/screener.py`, `backend/app/repositories/securities.py` (`search_securities(priced_only)`), `backend/app/api/routes/securities.py`, `backend/app/services/assistant/tools.py:86`, `backend/app/schemas/status.py`, `backend/app/api/routes/status.py`
- Modify: `frontend/src/features/screener/useScreener.ts`, `frontend/src/features/screener/ScreenerPage.tsx`, `frontend/src/app/MarketStatus.tsx`, `frontend/src/lib/api/schema.d.ts` (regenerated)
- Test: `backend/tests/test_api_screener.py`, `backend/tests/test_api_securities.py`, `backend/tests/test_api_status.py` (find the existing files with `grep -rln "/api/screener\|/api/status\|/api/securities" backend/tests`), `frontend/src/features/screener/ScreenerPage.test.tsx`, `frontend/src/app/MarketStatus.test.tsx` (create if absent)

**Interfaces:**
- Produces:
  - `GET /api/screener?kind=…&region=europe|us` (`region` optional; default = all); rows only for securities with a quote
  - `search_securities(..., priced_only: bool = False)`; public `GET /api/securities` passes `priced_only=not overridden`; the assistant's search passes `priced_only=True`
  - `StatusResponse.markets: list[MarketState]` with `MarketState(code: str, label: str, open: bool)` (`europe`/« Europe », `us`/« New York »); `market_open` kept (= Europe)
  - Explorer: « Europe » / « États-Unis » toggle (URL param `region`, default `europe`), query key `["screener", kind, region]`
  - Status: « Europe : ouverte · New York : fermée » style line

- [ ] **Step 1: Failing tests**

Backend:

```python
def test_screener_hides_unpriced_and_filters_region(client, db):
    paris = make_security(db, "MC.PA", market="Euronext Paris")
    ny = make_security(db, "AAPL", market="Nasdaq")
    make_security(db, "RAW.DE", market="Xetra")  # jamais coté sur Yahoo
    for s in (paris, ny):
        make_quote(db, s, 10.0)
    assert {r["yahoo_ticker"] for r in client.get("/api/screener").json()} == {"MC.PA", "AAPL"}
    assert [r["yahoo_ticker"] for r in client.get("/api/screener", params={"region": "us"}).json()] == ["AAPL"]
    assert [r["yahoo_ticker"] for r in client.get("/api/screener", params={"region": "europe"}).json()] == ["MC.PA"]


def test_search_hides_unpriced(client, db):
    make_security(db, "RAW.DE", market="Xetra", name="Raiffeisen")
    assert client.get("/api/securities", params={"q": "Raiff"}).json()["total"] == 0


def test_status_lists_each_place(client):
    markets = client.get("/api/status").json()["markets"]
    assert [(m["code"], m["label"]) for m in markets] == [("europe", "Europe"), ("us", "New York")]
```

Use the helpers that exist in `tests/factories.py` for quotes (grep `def make_quote` or how existing screener tests create `SecurityQuote`); adapt calls, not assertions.

Frontend (`ScreenerPage.test.tsx`, following the file's existing mocking of `apiGet`):

```tsx
it("switches region and refetches", async () => {
  // rendu de la page Actions : la requête part avec region=europe, puis region=us après clic sur « États-Unis »
  // attendre l'appel apiGet("/api/screener", { kind: "stock", region: "europe" })
  // cliquer sur le bouton « États-Unis » ; attendre apiGet("/api/screener", { kind: "stock", region: "us" })
});
```

Write it concretely with the mocks the file already uses (read it first). `MarketStatus.test.tsx`: render with a mocked status `{ market_open: false, markets: [{code:"europe",label:"Europe",open:false},{code:"us",label:"New York",open:true}], jobs: [], indices: [] }` and expect the texts « Europe : fermée » and « New York : ouverte ».

- [ ] **Step 2: Run** the backend files and `npx vitest run src/features/screener src/app` . Expected: FAIL.

- [ ] **Step 3: Implement**

Backend:
- `screener_rows(..., region: str | None = None)`: when `security_id is None`, add `.where(SecurityQuote.security_id.is_not(None))` and, for `region == "us"`, `.where(Security.market.in_(US_MARKETS))`, for `"europe"`, `.where(Security.market.not_in(US_MARKETS))`. Route: `region: Literal["europe", "us"] | None = None`.
- `search_securities(..., priced_only: bool = False)`: `.where(SecurityQuote.security_id.is_not(None))` when set. Route passes `priced_only=not overridden`; assistant `_search` passes `priced_only=True`.
- `schemas/status.py`: `class MarketState(BaseModel): code: str; label: str; open: bool`; `StatusResponse.markets: list[MarketState]`. Route: `now = datetime.now(UTC)`; `markets=[MarketState(code=c.code, label=c.label, open=c.is_open(now)) for c in CALENDARS]`.

Frontend:
- `useScreener(kind, region)` → `queryKey: ["screener", kind, region]`, params `{ kind, region }`. `useToggleFavorite` cancels `["screener"]` (prefix) — unchanged.
- `ScreenerPage`: `const region = params.get("region") === "us" ? "us" : "europe";` two buttons (same `Button` sizes/variants as the chart period buttons) above `ScreenerFilters`: « Europe » and « États-Unis », `aria-pressed`, `onClick={() => update("region", value === "europe" ? null : "us")}`.
- `MarketStatus`: replace the single line by one line per `data.markets` item: dot + `{m.label} : {m.open ? "ouverte" : "fermée"}`.
- Regenerate types: start the dev API on the new code, `npm run gen:api`.

- [ ] **Step 4: Run** backend files + full backend suite; `npx tsc -b`, `npx vitest run`, `npx oxlint < /dev/null`. Expected: PASS, 0 lint errors.

- [ ] **Step 5: Commit** — `feat: hide unpriced securities, Explorer by region, market status per place`

---

### Task 10: Docs, live load, measurements, e2e

**Files:**
- Modify: guide `docs/guide/…` (find pages naming the universe, sources, ETF eligibility, « Bourse ouverte »: `grep -rln "Euronext\|ETF\|Bourse ouverte\|devise" docs/guide docs/admin`), admin docs `docs/admin/donnees.md` (sources table, snapshots, `python -m app.seeds.snapshots`, `fx`, `daily_history_us`, `us_evening`, weekly fundamentals, postponed places), `docs/admin/base-de-donnees.md` (`fx_rates`, `securities.currency/source`, size ≈ 5–10 GB), `docs/admin/architecture.md`, `docs/admin/api.md` (`region`, `markets`), `README.md`, `CLAUDE.md` (universe line)
- Modify: e2e specs that assert « Bourse ouverte/fermée » or screener requests (`grep -rn "Bourse\|screener" frontend/e2e`)

- [ ] **Step 1: Docs** — write the changes above in French, short sentences. In `donnees.md`, a table « Source | Place | Fichier | Repli » mirroring the survey at the top of this plan, and a « Places reportées » paragraph (Londres, Madrid, Vienne, Varsovie, with the reason).

- [ ] **Step 2: e2e** — update specs, then run the e2e stack (Global Constraints). Expected: all pass.

- [ ] **Step 3: Live load and measurements** — rebuild the normal stack (`docker compose up -d --build api worker web`), let the worker's bootstrap run, and record in the ledger:
  - `SELECT source, count(*) FROM securities WHERE active GROUP BY source;`
  - `SELECT count(*) FROM securities WHERE active AND id NOT IN (SELECT security_id FROM security_quotes);`
  - durations from the worker log (`docker compose logs worker | grep "Fin de la tâche\|Début de la tâche"`) for `universe`, `quotes_t1/t2/t3`, `scores`, `fx`, `fundamentals`, `history_backfill`, compared with block C's values in `data_status` before the rebuild (capture `SELECT job, last_success_at, last_count FROM data_status` first);
  - `SELECT pg_size_pretty(pg_total_relation_size('daily_prices'));` at start and after one hour of backfill, plus `SELECT count(*) FILTER (WHERE history_complete), count(*) FROM securities WHERE active;` to estimate the remaining time.
  - `curl -s -o /dev/null -w "%{size_download} %{time_total}\n" "http://localhost:8095/api/screener?kind=stock&region=europe"` and `region=us`.
  If a quote tier pass takes longer than its interval during a session, raise `yahoo_chunk_size` in `config.py` (50 → 100), re-measure, and ledger the ruling with both timings.

- [ ] **Step 4: Full checks** — backend suite, `npx tsc -b`, `npx vitest run`, `npx oxlint < /dev/null`. Expected: PASS.

- [ ] **Step 5: Commit** — `docs: extended universe, sources, FX and per-place sessions`
