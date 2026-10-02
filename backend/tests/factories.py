from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Security, SecurityEnvelope, SecurityQuote, SecurityScore, User
from app.services.auth.accounts import TERMS_VERSION


def make_security(
    db: Session,
    ticker: str,
    *,
    kind: str = "stock",
    eligibility: str = "eligible",  # statut PEA
    pea_pme: str | None = None,     # statut PEA-PME (aucune ligne si None)
    country: str | None = "FR",
    active: bool = True,
    isin: str | None = None,
    name: str | None = None,
    market: str = "Euronext Paris",
) -> Security:
    security = Security(
        yahoo_ticker=ticker,
        symbol=ticker.split(".")[0],
        name=name or ticker,
        kind=kind,
        market=market,
        country=country,
        isin=isin,
        active=active,
    )
    security.envelopes.append(SecurityEnvelope(envelope="pea", status=eligibility, source="auto"))
    if pea_pme is not None:
        security.envelopes.append(SecurityEnvelope(envelope="pea_pme", status=pea_pme, source="auto"))
    db.add(security)
    db.flush()
    return security


def make_score(db: Session, security: Security, **fields) -> SecurityScore:
    values = dict(
        computed_at=datetime(2026, 9, 28, 8, 0, tzinfo=UTC), total=60.0, technical=60.0, fundamental=60.0,
        components=[], available_ratio=1.0, liquid=True, history_days=250, avg_turnover_eur=1_000_000.0,
        eligible_for_top=True, perf_1w=1.0, perf_1m=2.0, perf_3m=3.0, perf_1y=4.0, sparkline=[1.0, 2.0],
    )
    values.update(fields)
    score = SecurityScore(security_id=security.id, **values)
    db.add(score)
    db.flush()
    return score


_HASHES: dict[str, str] = {}  # Argon2 est volontairement lent : un hachage par mot de passe pour toute la session


def make_user(
    db: Session, email: str = "moi@example.com", *, first_name: str = "Jean", last_name: str = "Dupont",
    password: str | None = "motdepasse-solide", verified: bool = True, role: str = "user", is_premium: bool = False,
    terms_version: str | None = TERMS_VERSION,
) -> User:
    if password is not None and password not in _HASHES:
        _HASHES[password] = hash_password(password)
    user = User(
        email=email, first_name=first_name, last_name=last_name,
        password_hash=_HASHES[password] if password is not None else None,
        email_verified_at=datetime(2026, 9, 1, tzinfo=UTC) if verified else None, role=role, is_premium=is_premium,
        terms_version=terms_version, terms_accepted_at=datetime(2026, 9, 1, tzinfo=UTC) if terms_version else None,
    )
    db.add(user)
    db.flush()
    return user


def make_quote(db: Session, security: Security, price: float, *, change_pct: float | None = None,
               previous_close: float | None = None, as_of: datetime | None = None) -> SecurityQuote:
    quote = SecurityQuote(security_id=security.id, price=price, change_pct=change_pct, previous_close=previous_close,
                          volume=1000, as_of=as_of or datetime.now(UTC))
    db.merge(quote)
    db.flush()
    return db.get(SecurityQuote, security.id)


def make_subscription(db: Session, user: User, *, status: str = "active", interval: str = "month",
                      period_end: datetime | None = None, cancel: bool = False, sub_id: str | None = None,
                      customer_id: str | None = None) -> "Subscription":  # noqa: F821
    from app.models import Subscription

    row = Subscription(user_id=user.id, stripe_customer_id=customer_id or f"cus_{user.id.hex[:12]}",
                       stripe_subscription_id=sub_id or f"sub_{user.id.hex[:12]}", status=status, interval=interval,
                       current_period_end=period_end or datetime(2026, 11, 1, tzinfo=UTC), cancel_at_period_end=cancel)
    db.add(row)
    db.flush()
    return row
