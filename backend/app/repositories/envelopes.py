"""Statuts des enveloppes stockés par titre : recalcul, corrections manuelles, filtre SQL."""
from collections.abc import Iterable

from sqlalchemy import ColumnElement, exists

from app.models import Security, SecurityEnvelope, SecurityFundamentals
from app.seeds.loader import confirmed_pea_etfs
from app.services.envelopes.rules import ELIGIBLE, SecurityFacts, compute_envelopes, filtering_envelopes
from app.services.fx import to_eur


def facts_for(security: Security, fundamentals: SecurityFundamentals | None) -> SecurityFacts:
    f = fundamentals
    return SecurityFacts(
        kind=security.kind, country=security.country, industry=security.industry, name=security.name,
        confirmed_etf=security.kind == "etf" and security.yahoo_ticker in confirmed_pea_etfs(),
        employees=f.employees if f else None,
        # Devise inconnue : montant inconnu (PEA-PME « à vérifier ») plutôt que compté en euros.
        revenue_eur=to_eur(f.revenue, f.revenue_currency or f.currency, strict=True) if f else None,
        market_cap_eur=to_eur(f.market_cap, f.currency, strict=True) if f else None,
    )


def refresh_envelopes(security: Security, fundamentals: SecurityFundamentals | None) -> None:
    """Recalcule toutes les enveloppes à règle du titre ; les corrections manuelles sont conservées."""
    overrides = {e.envelope: e.override for e in security.envelopes}
    for code, result in compute_envelopes(facts_for(security, fundamentals), overrides).items():
        row = security.envelope(code)
        if row is None:
            row = SecurityEnvelope(envelope=code)
            security.envelopes.append(row)
        row.status, row.source, row.override = result.status, result.source, result.override


def set_envelope_override(security: Security, code: str, override: str | None,
                          fundamentals: SecurityFundamentals | None) -> None:
    """Correction manuelle (None = revenir au calcul automatique ou à la liste de départ)."""
    refresh_envelopes(security, fundamentals)  # crée la ligne si elle manque encore
    security.envelope(code).override = override
    refresh_envelopes(security, fundamentals)


def envelope_clause(codes: Iterable[str]) -> ColumnElement[bool] | None:
    """Condition « éligible à au moins une de ces enveloppes » ; None = pas de filtre (rien choisi ou compte-titres)."""
    wanted = filtering_envelopes(codes)
    if not wanted:
        return None
    return exists().where(
        SecurityEnvelope.security_id == Security.id,
        SecurityEnvelope.envelope.in_(sorted(wanted)),
        SecurityEnvelope.status == ELIGIBLE,
    )
