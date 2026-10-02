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
