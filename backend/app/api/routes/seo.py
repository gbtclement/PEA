"""Fichiers destinés aux moteurs de recherche et aux IA, servis à la racine du site par nginx.

Tant que `SEO_INDEXING` est faux (local ou privé), robots.txt interdit tout. En ligne, seules les pages
publiques sont autorisées ; les pages personnelles (portefeuille, assistant, réglages) ne le sont jamais.
"""
from typing import Annotated
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.brand import APP_NAME
from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.models import Security

router = APIRouter(prefix="/seo", tags=["seo"])

PUBLIC_PATHS = ["/", "/explorer", "/etf", "/premium", "/cgv"]
PRIVATE_PATHS = ["/portefeuille", "/assistant", "/reglages"]
# Les pages sont rendues dans le navigateur : les robots doivent pouvoir lire les données publiques de l'API,
# seules les données personnelles leur sont fermées.
PRIVATE_API_PATHS = ["/api/portfolio", "/api/orders", "/api/assistant/", "/api/settings", "/api/favorites/", "/api/billing/"]

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]


def _url(settings: Settings, path: str) -> str:
    return settings.public_base_url.rstrip("/") + path


def _public_securities():
    return (Security.active.is_(True), Security.eligibility == "eligible", Security.kind.in_(("stock", "etf")))


@router.get("/robots.txt")
def robots(settings: SettingsDep) -> Response:
    lines = ["User-agent: *"]
    if not settings.seo_indexing:
        lines.append("Disallow: /")
    else:
        lines += ["Allow: /$", "Allow: /explorer", "Allow: /etf", "Allow: /premium$", "Allow: /cgv", "Allow: /titres/", "Allow: /llms.txt"]
        lines += [f"Disallow: {path}" for path in PRIVATE_PATHS]
        lines += [f"Disallow: {path}" for path in PRIVATE_API_PATHS]
        lines += ["", f"Sitemap: {_url(settings, '/sitemap.xml')}"]
    return Response("\n".join(lines) + "\n", media_type="text/plain")


@router.get("/sitemap.xml")
def sitemap(settings: SettingsDep, db: DbDep) -> Response:
    ids = db.scalars(select(Security.id).where(*_public_securities()).order_by(Security.id))
    paths = PUBLIC_PATHS + [f"/titres/{security_id}" for security_id in ids]
    urls = "".join(f"<url><loc>{escape(_url(settings, path))}</loc></url>" for path in paths)
    body = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    return Response(body, media_type="application/xml")


@router.get("/llms.txt")
def llms(settings: SettingsDep, db: DbDep) -> Response:
    counts = dict(db.execute(select(Security.kind, func.count()).where(*_public_securities()).group_by(Security.kind)).all())
    stocks, etfs = counts.get("stock", 0), counts.get("etf", 0)
    body = f"""# {APP_NAME}

> Radar des actions et ETF : top 10 du moment selon un score mixte technique et fondamental, explorateur, fiches détaillées avec graphiques et simulateur « et si j'avais investi ». Outil d'aide à la décision et d'apprentissage, pas un conseil en investissement.

Suivi actuel : {stocks} action{"s" if stocks > 1 else ""} et {etfs} ETF (Euronext, Xetra, Madrid…). Cours issus de Yahoo Finance, en différé.

## Pages

- [Accueil]({_url(settings, "/")}) : top 10 du moment avec l'explication de chaque score, indices, hausses et baisses du jour, carte du marché.
- [Explorer]({_url(settings, "/explorer")}) : toutes les actions avec score, performances (1 jour à 1 an), PER, rendement et enveloppes compatibles (PEA…), triables et filtrables.
- [ETF]({_url(settings, "/etf")}) : ETF classés par score technique.
- Fiches titres ({_url(settings, "/titres/")}<id>) : cours, graphique en chandeliers avec moyennes mobiles, RSI et MACD, détail du score, données fondamentales, actualités, simulateur d'achat passé frais inclus.

## Méthode du score

- Score sur 100 : moitié technique (tendance, force relative face au CAC 40, RSI, MACD), moitié fondamentale (valorisation, croissance, bilan, dividende). Les ETF sont notés sur la partie technique seule.
- Le top 10 exclut les titres peu échangés ou à l'historique trop court.
- La compatibilité avec le PEA est déduite du pays du siège (code ISIN) : à confirmer auprès de son courtier.

## Plan du site

- [sitemap.xml]({_url(settings, "/sitemap.xml")})
"""
    return Response(body, media_type="text/markdown; charset=utf-8")
