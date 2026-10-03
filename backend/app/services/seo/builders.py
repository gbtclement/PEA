"""Contenu de chaque page publique : mêmes données que les routes JSON, même texte que le frontend."""
from html import escape

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.routes.rankings import get_top
from app.api.routes.security_detail import get_security
from app.core.brand import APP_NAME
from app.models import User
from app.repositories.screener import ScreenerQuery, screener_page
from app.schemas.auth import MeOut
from app.schemas.screener import ScreenerPage as ScreenerPageOut
from app.schemas.screener import ScreenerRow
from app.schemas.security_detail import SecurityDetail
from app.services.envelopes.rules import ENVELOPES
from app.services.seo.page import (
    DEFAULT_DESCRIPTION, LISTS, STATIC_PAGES, PageContent, breadcrumb, money, pct, web_application,
)

PAGE_SIZE = 50  # comme PAGE_SIZE de features/screener/useScreener.ts


def js_round(value: float) -> int:
    """Arrondi comme Math.round du frontend (0,5 vers le haut), pas l'arrondi bancaire de Python."""
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


def _me(user: User | None) -> tuple[list, object]:
    return ["me"], (MeOut.model_validate(user).model_dump(mode="json") if user else None)


def account_key(user: User | None) -> str:
    """Comme useAccountKey() du frontend : identifiant du compte, ou « visiteur »."""
    return str(user.id) if user else "visiteur"


def security_meta(detail: SecurityDetail) -> tuple[str, str]:
    """Titre et description d'une fiche — frontend : securityMeta dans features/security/SecurityPage.tsx."""
    etf = detail.kind == "etf"
    score = f"score {APP_NAME} {js_round(detail.score)}/100, " if detail.score is not None else ""
    envelopes = (f"Enveloppes compatibles : {', '.join(ENVELOPES[c] for c in detail.envelopes)}."
                 if detail.envelopes else "")
    title = f"{detail.name} ({detail.symbol}) — cours, score et analyse"
    fundamentals = "" if etf else "données fondamentales, "
    description = (f"{detail.name} ({detail.symbol}, {detail.market}) : cours, {score}graphique en chandeliers, "
                   f"{fundamentals}actualités et simulateur. {envelopes}")
    return title, description


def security_page(db: Session, user: User | None, security_id: int, base_url: str) -> PageContent:
    try:
        detail = get_security(security_id, db, user)
    except HTTPException:
        return PageContent(title="Titre introuvable", description=DEFAULT_DESCRIPTION, path=f"/titres/{security_id}",
                           summary_html="<h1>Titre introuvable</h1>", noindex=True, status=404, data=[_me(user)])
    title, description = security_meta(detail)
    path = f"/titres/{detail.id}"
    json_ld: list[dict] = []
    if detail.kind != "index":
        item = {"@context": "https://schema.org", "@type": "InvestmentFund" if detail.kind == "etf" else "Corporation",
                "name": detail.name, "tickerSymbol": detail.symbol, "url": f"{base_url}{path}"}
        if detail.isin:
            item["identifier"] = detail.isin
        if detail.kind != "etf" and detail.industry:
            item["industry"] = detail.industry
        json_ld.append(item)
    section = ("ETF", "/etf") if detail.kind == "etf" else ("Explorer", "/explorer")
    json_ld.append(breadcrumb(base_url, [("Accueil", "/"), section, (detail.name, path)]))
    reasons = [c.message for c in (detail.score_detail.components if detail.score_detail else [])]
    parts = [
        f"<article><h1>{escape(detail.name)}</h1>",
        f"<p>{escape(detail.symbol)} · {escape(detail.market)}" + (f" · {escape(detail.isin)}" if detail.isin else "") + "</p>",
        f"<p>Cours : {escape(money(detail.price, detail.currency))} ({escape(pct(detail.change_pct))} aujourd'hui)</p>",
    ]
    if detail.score is not None:
        parts.append(f"<p>Score : {js_round(detail.score)}/100</p>")
    if reasons:
        parts.append("<ul>" + "".join(f"<li>{escape(r)}</li>" for r in reasons) + "</ul>")
    if detail.sector:
        parts.append(f"<p>Secteur : {escape(detail.sector)}</p>")
    if detail.envelopes:
        parts.append(f"<p>Enveloppes compatibles : {escape(', '.join(ENVELOPES[c] for c in detail.envelopes))}</p>")
    parts.append("</article>")
    return PageContent(title=title, description=description, path=path, summary_html="".join(parts), json_ld=json_ld,
                       data=[_me(user), (["security", detail.id], detail.model_dump(mode="json"))])


def home_page(db: Session, user: User | None, base_url: str) -> PageContent:
    top = get_top(10, db, user)
    items = []
    for t in top:
        score = js_round(t.score) if t.score is not None else "—"
        reasons = "<ul>" + "".join(f"<li>{escape(r)}</li>" for r in t.reasons) + "</ul>" if t.reasons else ""
        items.append(f'<li><a href="/titres/{t.id}">{escape(t.name)}</a> ({escape(t.symbol)}) — '
                     f"{escape(money(t.price, t.currency))}, score {score}/100{reasons}</li>")
    summary = (f"<section><h1>Accueil</h1><p>{escape(DEFAULT_DESCRIPTION)}</p>"
               f"<h2>Top 10 du moment</h2><ol>{''.join(items)}</ol></section>")
    return PageContent(title=None, description=DEFAULT_DESCRIPTION, path="/", summary_html=summary,
                       json_ld=[web_application(base_url)],
                       data=[_me(user), (["top", account_key(user)], [t.model_dump(mode="json") for t in top])])


def list_page(db: Session, user: User | None, path: str, base_url: str) -> PageContent:
    title, description = LISTS[path]
    kind = "etf" if path == "/etf" else "stock"
    # Première page telle que le navigateur la demande (Europe, tri par nom, sans filtre) : même clé de cache.
    rows, total = screener_page(db, user.id if user else None, ScreenerQuery(kind=kind, region="europe"),
                                limit=PAGE_SIZE, offset=0)
    items = "".join(f'<li><a href="/titres/{row[0].id}">{escape(row[0].name)}</a> ({escape(row[0].symbol)})</li>'
                    for row in rows)
    summary = f"<section><h1>{escape(title)}</h1><p>{escape(description)}</p><ul>{items}</ul></section>"
    first_page = {"pages": [ScreenerPageOut(items=[ScreenerRow.build(row) for row in rows], total=total)
                            .model_dump(mode="json")], "pageParams": [0]}
    return PageContent(title=title, description=description, path=path, summary_html=summary,
                       json_ld=[breadcrumb(base_url, [("Accueil", "/"), (title, path)])],
                       data=[_me(user), (["screener", kind, "europe", "name", "asc", ""], first_page)])


def static_page(user: User | None, path: str) -> PageContent:
    title, description = STATIC_PAGES[path]
    return PageContent(title=title, description=description, path=path,
                       summary_html=f"<article><h1>{escape(title)}</h1><p>{escape(description)}</p></article>",
                       data=[_me(user)])


def build_page(db: Session, user: User | None, path: str, base_url: str) -> PageContent | None:
    """Page publique demandée, ou None (page privée ou inconnue : nginx ne l'envoie pas ici)."""
    if path == "/":
        return home_page(db, user, base_url)
    if path in LISTS:
        return list_page(db, user, path, base_url)
    if path in STATIC_PAGES:
        return static_page(user, path)
    if path.startswith("/titres/") and path[len("/titres/"):].isdigit():
        return security_page(db, user, int(path[len("/titres/"):]), base_url)
    return None
