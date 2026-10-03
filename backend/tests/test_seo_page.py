"""HTML enrichi des pages publiques (bloc F) : balises d'en-tête, résumé lisible sans JavaScript, données embarquées."""
import json
import re
from datetime import UTC, datetime

import pytest

from app.api.routes.seo import get_spa_template
from app.core.config import Settings, get_settings
from app.models import SecurityQuote
from tests.factories import make_score, make_security

TEMPLATE = """<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <title>Cotalyx</title>
    <meta name="description" content="défaut" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/assets/index.js"></script>
  </body>
</html>
"""
AS_OF = datetime(2026, 10, 2, 15, 35, tzinfo=UTC)


def _quote(db, security, price=600.0, change=1.5):
    db.add(SecurityQuote(security_id=security.id, price=price, previous_close=price, change_pct=change, volume=1, as_of=AS_OF))
    db.flush()


def _data(html: str) -> list:
    match = re.search(r'<script id="cotalyx-data" type="application/json">(.*?)</script>', html, re.S)
    assert match, "données embarquées absentes"
    return json.loads(match.group(1))


def _keys(html: str) -> list:
    return [entry[0] for entry in _data(html)]


@pytest.fixture
def pages(anon_client):
    anon_client.app.dependency_overrides[get_spa_template] = lambda: TEMPLATE
    anon_client.app.dependency_overrides[get_settings] = lambda: Settings(public_base_url="https://cotalyx.test")
    yield anon_client
    anon_client.app.dependency_overrides.clear()


def _get(test_client, path):
    return test_client.get("/api/seo/page", params={"path": path})


def test_security_page_has_head_summary_and_data(pages, db):
    lvmh = make_security(db, "MC.PA", name="LVMH", isin="FR0000121014")
    _quote(db, lvmh)
    make_score(db, lvmh, total=82.4, components=[
        {"key": "trend", "label": "Tendance", "points": 20, "max_points": 20, "message": "✅ Tendance haussière", "group": "technical"}])
    response = _get(pages, f"/titres/{lvmh.id}")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
    html = response.text
    assert "<title>LVMH (MC) — cours, score et analyse | Cotalyx</title>" in html
    assert html.count("<title>") == 1 and 'content="défaut"' not in html
    assert (f'<meta name="description" content="LVMH (MC, Euronext Paris) : cours, score Cotalyx 82/100, graphique en chandeliers, '
            "données fondamentales, actualités et simulateur. Enveloppes compatibles : PEA.") in html
    assert f'<link rel="canonical" href="https://cotalyx.test/titres/{lvmh.id}"' in html
    assert '<meta property="og:title" content="LVMH (MC) — cours, score et analyse | Cotalyx"' in html
    assert '"@type": "Corporation"' in html and '"@type": "BreadcrumbList"' in html
    root = html.split('<div id="root">')[1].split("</div>\n")[0]
    assert "LVMH" in root and "600,00 €" in root and "Tendance haussière" in root
    assert ["security", str(lvmh.id)] in _keys(html)
    assert ["me"] in _keys(html)


def test_unknown_security_is_404_noindex(pages):
    response = _get(pages, "/titres/99999999")
    assert response.status_code == 404
    assert '<meta name="robots" content="noindex, nofollow"' in response.text
    assert "Titre introuvable" in response.text


def test_home_and_lists(pages, db):
    lvmh = make_security(db, "MC.PA", name="LVMH")
    _quote(db, lvmh)
    make_score(db, lvmh, total=80.0)
    home = _get(pages, "/").text
    assert "<title>Cotalyx</title>" in home and "LVMH" in home.split('<div id="root">')[1]
    assert ["top", "visiteur"] in _keys(home)
    explorer = _get(pages, "/explorer").text
    assert "<title>Explorer | Cotalyx</title>" in explorer
    assert f'href="/titres/{lvmh.id}"' in explorer
    # Première page de la liste, sous la clé du navigateur (filtres par défaut) : affichée sans requête.
    first_page = dict((json.dumps(k), v) for k, v in _data(explorer))[json.dumps(["screener", "stock", "europe", "name", "asc", ""])]
    assert first_page["pageParams"] == [0] and first_page["pages"][0]["total"] == 1
    assert first_page["pages"][0]["items"][0]["name"] == "LVMH"


def test_static_public_pages(pages):
    cgu = _get(pages, "/cgu").text
    assert "<title>Conditions générales d'utilisation | Cotalyx</title>" in cgu
    assert "<title>Premium | Cotalyx</title>" in _get(pages, "/premium").text


def test_page_escapes_names_and_json(pages, db):
    bad = make_security(db, "BAD.PA", name='A <b>&"x"</b></script>')
    _quote(db, bad)
    html = _get(pages, f"/titres/{bad.id}").text
    assert "<b>" not in html
    script = html.split('<script id="cotalyx-data" type="application/json">')[1].split("</script>")[0]
    assert "</" not in script  # « </script> » dans un nom ne peut pas fermer la balise
    assert _data(html)  # reste un JSON valide


def test_page_html_is_never_publicly_cached(pages, db):
    response = _get(pages, "/")
    assert "private" in response.headers["cache-control"] and "no-cache" in response.headers["cache-control"]


def test_page_falls_back_when_template_missing(anon_client):
    def broken():
        raise RuntimeError("web injoignable")

    anon_client.app.dependency_overrides[get_spa_template] = broken
    try:
        assert anon_client.get("/api/seo/page", params={"path": "/"}).status_code == 503
    finally:
        anon_client.app.dependency_overrides.clear()


def test_private_or_unknown_paths_are_refused(pages):
    assert _get(pages, "/portefeuille").status_code == 404
    assert _get(pages, "/titres/abc").status_code == 404


def test_signed_in_member_gets_his_own_data(client, user, db):
    client.app.dependency_overrides[get_spa_template] = lambda: TEMPLATE
    try:
        html = client.get("/api/seo/page", params={"path": "/"}).text
    finally:
        client.app.dependency_overrides.clear()
    entries = dict((json.dumps(key), value) for key, value in _data(html))
    assert entries[json.dumps(["me"])]["email"] == "moi@example.com"
    assert json.dumps(["top", str(user.id)]) in entries


MANIFEST = {
    "index.html": {"file": "assets/index-a.js", "isEntry": True, "imports": ["_react-r.js"]},
    "_react-r.js": {"file": "assets/react-r.js"},
    "_gauge-g.js": {"file": "assets/gauge-g.js", "imports": ["_react-r.js"]},
    "src/features/security/SecurityPage.tsx": {
        "file": "assets/SecurityPage-s.js", "isDynamicEntry": True, "imports": ["_react-r.js", "_gauge-g.js", "index.html"]},
}


def test_page_preloads_the_code_of_its_route(pages, db):
    # Le code de la fiche part en même temps que celui de l'application, sans attendre le démarrage de React.
    from app.api.routes.seo import get_spa_manifest

    pages.app.dependency_overrides[get_spa_manifest] = lambda: MANIFEST
    lvmh = make_security(db, "MC.PA", name="LVMH")
    _quote(db, lvmh)
    html = _get(pages, f"/titres/{lvmh.id}").text
    head = html.split("</head>")[0]
    assert '<link rel="modulepreload" href="/assets/SecurityPage-s.js" />' in head
    assert '<link rel="modulepreload" href="/assets/gauge-g.js" />' in head
    assert "react-r.js" not in head and "index-a.js" not in head  # déjà chargés par index.html


def test_page_works_without_manifest(pages, db):
    from app.api.routes.seo import get_spa_manifest

    def broken():
        raise RuntimeError("manifeste absent")

    pages.app.dependency_overrides[get_spa_manifest] = broken
    response = _get(pages, "/")
    assert response.status_code == 200 and "modulepreload" not in response.text
