"""Fichiers destinés aux moteurs de recherche et aux IA, servis à la racine du site par nginx.

Tant que `SEO_INDEXING` est faux (local ou privé), robots.txt interdit tout. En ligne, seules les pages
publiques sont autorisées ; les pages personnelles (portefeuille, assistant, réglages) ne le sont jamais.
"""
import logging
import time
from typing import Annotated
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.cache import cache_control
from app.core.brand import APP_NAME
from app.core.config import Settings, get_settings
from app.core.current_user import get_optional_user
from app.core.db import get_db
from app.models import Security, User

router = APIRouter(prefix="/seo", tags=["seo"])
logger = logging.getLogger(__name__)

PUBLIC_PATHS = ["/", "/explorer", "/etf", "/premium", "/cgv"]
PRIVATE_PATHS = ["/portefeuille", "/assistant", "/reglages"]
# Les pages sont rendues dans le navigateur : les robots doivent pouvoir lire les données publiques de l'API,
# seules les données personnelles leur sont fermées.
PRIVATE_API_PATHS = ["/api/portfolio", "/api/orders", "/api/assistant/", "/api/settings", "/api/favorites/", "/api/billing/"]

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]
SEO_FILES_MAX_AGE = 3600  # une heure : les robots relisent ces fichiers souvent


def _url(settings: Settings, path: str) -> str:
    return settings.public_base_url.rstrip("/") + path


def _public_securities():
    return (Security.active.is_(True), Security.kind.in_(("stock", "etf")))


@router.get("/robots.txt")
def robots(request: Request, settings: SettingsDep) -> Response:
    lines = ["User-agent: *"]
    if not settings.seo_indexing:
        lines.append("Disallow: /")
    else:
        lines += ["Allow: /$", "Allow: /explorer", "Allow: /etf", "Allow: /premium$", "Allow: /cgv", "Allow: /titres/", "Allow: /llms.txt"]
        lines.append("Allow: /api/billing/plans")  # prix publics de la page /premium (avant la règle /api/billing/)
        lines += [f"Disallow: {path}" for path in PRIVATE_PATHS]
        lines += [f"Disallow: {path}" for path in PRIVATE_API_PATHS]
        lines += ["", f"Sitemap: {_url(settings, '/sitemap.xml')}"]
    return Response("\n".join(lines) + "\n", media_type="text/plain", headers=cache_control(request, SEO_FILES_MAX_AGE))


@router.get("/sitemap.xml")
def sitemap(request: Request, settings: SettingsDep, db: DbDep) -> Response:
    ids = db.scalars(select(Security.id).where(*_public_securities()).order_by(Security.id))
    paths = PUBLIC_PATHS + [f"/titres/{security_id}" for security_id in ids]
    urls = "".join(f"<url><loc>{escape(_url(settings, path))}</loc></url>" for path in paths)
    body = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
    return Response(body, media_type="application/xml", headers=cache_control(request, SEO_FILES_MAX_AGE))


@router.get("/llms.txt")
def llms(request: Request, settings: SettingsDep, db: DbDep) -> Response:
    counts = dict(db.execute(select(Security.kind, func.count()).where(*_public_securities()).group_by(Security.kind)).all())
    stocks, etfs = counts.get("stock", 0), counts.get("etf", 0)
    body = f"""# {APP_NAME}

> Radar des actions et ETF : top 10 du moment selon un score mixte technique et fondamental, explorateur, fiches détaillées avec graphiques et simulateur « et si j'avais investi ». Outil d'aide à la décision et d'apprentissage, pas un conseil en investissement.

Suivi actuel : {stocks} action{"s" if stocks > 1 else ""} et {etfs} ETF (Euronext, Francfort, Suisse, pays nordiques, États-Unis). Cours issus de Yahoo Finance, en différé, convertis en euros au cours de change du jour quand il le faut.

## Pages

- [Accueil]({_url(settings, "/")}) : top 10 du moment avec l'explication de chaque score, indices, hausses et baisses du jour, carte du marché.
- [Explorer]({_url(settings, "/explorer")}) : toutes les actions avec score, performances (1 jour à 1 an), PER, rendement et enveloppes compatibles (PEA, PEA-PME, compte-titres), triables et filtrables, par région (Europe ou États-Unis).
- [ETF]({_url(settings, "/etf")}) : ETF classés par score technique.
- Fiches titres ({_url(settings, "/titres/")}<id>) : cours, graphique en chandeliers avec moyennes mobiles, RSI et MACD, détail du score, données fondamentales, actualités, simulateur d'achat passé frais inclus.

## Méthode du score

- Score sur 100 : moitié technique (tendance, force relative face au CAC 40, RSI, MACD), moitié fondamentale (valorisation, croissance, bilan, dividende). Les ETF sont notés sur la partie technique seule.
- Le top 10 exclut les titres peu échangés ou à l'historique trop court.
- Enveloppes : le compte-titres accepte tous les titres. La compatibilité avec le PEA est déduite du pays du siège (code ISIN) pour une action ; un ETF n'est indiqué compatible que si c'est confirmé ou si son nom contient « PEA ». À confirmer auprès de son courtier.

## Plan du site

- [sitemap.xml]({_url(settings, "/sitemap.xml")})
"""
    return Response(body, media_type="text/markdown; charset=utf-8", headers=cache_control(request, SEO_FILES_MAX_AGE))


# --- Pages publiques en HTML enrichi (nginx y envoie /, /explorer, /etf, /titres/<id>, /premium et pages légales) ---

_TEMPLATE_CACHE: dict[str, tuple[float, str]] = {}
TEMPLATE_TTL_SECONDS = 60


def get_spa_template(settings: Settings = Depends(get_settings)) -> str:
    """index.html construit par Vite, lu dans le conteneur web (gardé une minute)."""
    cached = _TEMPLATE_CACHE.get(settings.spa_template_url)
    if cached and time.monotonic() - cached[0] < TEMPLATE_TTL_SECONDS:
        return cached[1]
    response = httpx.get(settings.spa_template_url, timeout=2)
    response.raise_for_status()
    _TEMPLATE_CACHE[settings.spa_template_url] = (time.monotonic(), response.text)
    return response.text


def _load_template(request: Request, settings: Settings) -> str:
    # Appelé ici plutôt qu'en dépendance : une panne doit donner 503 (nginx sert alors le index.html statique).
    loader = request.app.dependency_overrides.get(get_spa_template)
    return loader() if loader else get_spa_template(settings)


@router.get("/page", response_class=HTMLResponse, include_in_schema=False)
def page(request: Request, settings: SettingsDep, db: DbDep, path: str = Query(..., max_length=200),
         user: User | None = Depends(get_optional_user)) -> HTMLResponse:
    from app.services.seo.builders import build_page  # import tardif : les routes JSON importent ce module
    from app.services.seo.page import render_page

    base_url = settings.public_base_url.rstrip("/")
    content = build_page(db, user, path, base_url)
    if content is None:
        raise HTTPException(status_code=404, detail="Page inconnue")
    try:
        template = _load_template(request, settings)
    except Exception:
        logger.warning("Gabarit index.html indisponible", exc_info=True)
        raise HTTPException(status_code=503, detail="Gabarit indisponible")
    # Contenu propre au compte (favoris, enveloppes) : jamais mis en cache par un intermédiaire.
    return HTMLResponse(render_page(template, content, base_url), status_code=content.status,
                        headers={"Cache-Control": "private, no-cache"})
