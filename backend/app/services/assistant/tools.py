from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.orders import paris_today
from app.api.routes.portfolio import get_portfolio
from app.api.routes.rankings import get_top
from app.api.routes.security_detail import get_security, simulate_since
from app.models import Security, User
from app.repositories.market_data import all_daily_prices
from app.repositories.securities import search_securities
from app.services.indicators import macd, performance, rsi, sma

HISTORY_DAYS = {"1M": 31, "6M": 183, "1Y": 365, "5Y": 365 * 5}
MAX_POINTS = 60


class ToolError(Exception):
    """Erreur renvoyée à Claude comme résultat d'outil (is_error)."""


TOOL_LABELS = {
    "search_securities": "Recherche de titres",
    "get_security_overview": "Fiche du titre",
    "get_price_history": "Historique des cours",
    "get_top10": "Top 10",
    "get_portfolio": "Votre portefeuille",
    "simulate_past_investment": "Simulation d'achat passé",
    "web_search": "Recherche web",
}

_TICKER = {"type": "string", "description": "Ticker Yahoo (ex. MC.PA) ou symbole (ex. MC)."}
TOOL_SPECS: list[dict] = [
    {"name": "search_securities",
     "description": "Cherche des actions ou ETF par nom, ticker ou ISIN. Renvoie ticker, cours, variation du jour et éligibilité PEA.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Texte recherché"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["query"]}},
    {"name": "get_security_overview",
     "description": "Fiche complète d'un titre : cours et horodatage, score détaillé (composants et explications), fondamentaux, éligibilité PEA.",
     "input_schema": {"type": "object", "properties": {"ticker": _TICKER}, "required": ["ticker"]}},
    {"name": "get_price_history",
     "description": "Clôtures journalières d'un titre sur une période (échantillonnées, 60 points maximum) avec RSI 14, moyennes mobiles 50/200, MACD et performance.",
     "input_schema": {"type": "object", "properties": {
         "ticker": _TICKER, "period": {"type": "string", "enum": list(HISTORY_DAYS)}}, "required": ["ticker", "period"]}},
    {"name": "get_top10",
     "description": "Top 10 actuel de l'application (actions éligibles PEA les mieux notées) avec les 3 principales raisons de chaque score.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_portfolio",
     "description": "Portefeuille de l'utilisateur : positions, PRU, plus/moins-values, répartition par secteur, compteur d'ordres de l'année.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "simulate_past_investment",
     "description": "Simule un achat passé : combien vaudrait aujourd'hui un montant investi à une date donnée, frais de courtage inclus (grille de l'utilisateur).",
     "input_schema": {"type": "object", "properties": {
         "ticker": _TICKER, "amount": {"type": "number", "description": "Montant en euros"},
         "date": {"type": "string", "description": "Date d'achat AAAA-MM-JJ"}}, "required": ["ticker", "amount", "date"]}},
]


def tool_label(name: str) -> str:
    return TOOL_LABELS.get(name, name)


def _resolve(db: Session, ticker: object) -> Security:
    if not isinstance(ticker, str) or not ticker.strip():
        raise ToolError("Paramètre ticker manquant.")
    value = ticker.strip().upper()
    base = select(Security).where(Security.active.is_(True), Security.kind != "index")
    found = db.scalars(base.where(func.upper(Security.yahoo_ticker) == value)).first()
    if found is None:
        # symbole seul : priorité aux titres éligibles, puis à Paris
        candidates = list(db.scalars(base.where(func.upper(Security.symbol) == value)))
        candidates.sort(key=lambda s: (s.eligibility != "eligible", not s.yahoo_ticker.endswith(".PA")))
        found = candidates[0] if candidates else None
    if found is None:
        raise ToolError(f"Titre introuvable : {ticker}. Utilisez search_securities pour trouver le bon ticker.")
    return found


def _search(db: Session, user: User, args: dict) -> list[dict]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolError("Paramètre query manquant.")
    limit = args.get("limit") if isinstance(args.get("limit"), int) else 8
    rows, _ = search_securities(db, q=query, kind=None, eligibility=None, limit=max(1, min(limit, 10)), offset=0)
    return [{"ticker": s.yahoo_ticker, "symbol": s.symbol, "name": s.name, "kind": s.kind, "market": s.market,
             "eligibility": s.eligibility, "price": q.price if q else None, "change_pct": q.change_pct if q else None}
            for s, q in rows]


def _overview(db: Session, user: User, args: dict) -> dict:
    security = _resolve(db, args.get("ticker"))
    return get_security(security.id, db=db, user=user).model_dump(mode="json", exclude={"sparkline"})


def _last(values: list) -> float | None:
    value = values[-1] if values else None
    return round(value, 2) if value is not None else None


def _history(db: Session, user: User, args: dict) -> dict:
    period = args.get("period")
    if period not in HISTORY_DAYS:
        raise ToolError("Période invalide : utilisez 1M, 6M, 1Y ou 5Y.")
    security = _resolve(db, args.get("ticker"))
    prices = all_daily_prices(db, security.id)
    if not prices:
        raise ToolError(f"Pas d'historique pour {security.name}.")
    values = [p.close for p in prices]
    since = prices[-1].date - timedelta(days=HISTORY_DAYS[period])
    window = [p for p in prices if p.date >= since]
    step = max(1, -(-len(window) // MAX_POINTS))
    sampled = window[::-1][::step][::-1]  # garde toujours la dernière clôture
    m = macd(values)
    return {
        "ticker": security.yahoo_ticker, "name": security.name, "period": period,
        "currency_note": "cours en devise de cotation",
        "first_date": window[0].date.isoformat(), "last_date": window[-1].date.isoformat(),
        "closes": [{"date": p.date.isoformat(), "close": round(p.close, 4)} for p in sampled],
        "min": round(min(p.close for p in window), 4), "max": round(max(p.close for p in window), 4),
        "performance_pct": performance([p.close for p in window], len(window) - 1),
        "indicators": {"rsi14": _last(rsi(values)), "sma50": _last(sma(values, 50)), "sma200": _last(sma(values, 200)),
                       "macd": _last(m.macd), "macd_signal": _last(m.signal)},
    }


def _top(db: Session, user: User, args: dict) -> list[dict]:
    fields = {"yahoo_ticker", "symbol", "name", "sector", "price", "change_pct", "score", "technical", "fundamental",
              "reasons", "perf_1m", "perf_1y", "pe", "dividend_yield"}
    return [{"rank": i + 1, **item.model_dump(mode="json", include=fields)}
            for i, item in enumerate(get_top(10, db=db, user=user))]


def _portfolio(db: Session, user: User, args: dict) -> dict:
    return get_portfolio(db=db, user=user).model_dump(mode="json")


def _simulate(db: Session, user: User, args: dict) -> dict:
    amount = args.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 < amount <= 1_000_000:
        raise ToolError("Montant invalide : entre 0 et 1 000 000 €.")
    try:
        start = date.fromisoformat(str(args.get("date")))
    except ValueError:
        raise ToolError("Date invalide : format AAAA-MM-JJ attendu.") from None
    if start >= paris_today():
        raise ToolError("La date doit être dans le passé.")
    security = _resolve(db, args.get("ticker"))
    return simulate_since(db, user.id, security.id, float(amount), start).model_dump(mode="json")


_HANDLERS = {"search_securities": _search, "get_security_overview": _overview, "get_price_history": _history,
             "get_top10": _top, "get_portfolio": _portfolio, "simulate_past_investment": _simulate}


def run_tool(db: Session, user: User, name: str, tool_input: dict) -> dict | list:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ToolError(f"Outil inconnu : {name}")
    if not isinstance(tool_input, dict):
        raise ToolError("Paramètres invalides.")
    return handler(db, user, tool_input)
