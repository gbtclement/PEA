import xml.etree.ElementTree as ET

import pytest

from app.core.config import Settings, get_settings
from tests.factories import make_security

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


@pytest.fixture
def online(client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(seo_indexing=True, public_base_url="https://pea.example/")
    yield client
    client.app.dependency_overrides.pop(get_settings)


def test_robots_disallows_everything_by_default(client):
    client.app.dependency_overrides[get_settings] = lambda: Settings(seo_indexing=False)
    response = client.get("/api/seo/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    lines = response.text.splitlines()
    assert "User-agent: *" in lines
    assert "Disallow: /" in lines
    assert "Sitemap" not in response.text


def test_robots_online_allows_public_pages_only(online):
    text = online.get("/api/seo/robots.txt").text
    lines = text.splitlines()
    assert "Disallow: /" not in lines
    for line in ("Allow: /$", "Allow: /explorer", "Allow: /etf", "Allow: /titres/", "Allow: /llms.txt",
                 "Disallow: /portefeuille", "Disallow: /assistant", "Disallow: /reglages"):
        assert line in lines
    # Les pages sont rendues côté navigateur : Google doit pouvoir lire les données publiques de l'API
    assert "Disallow: /api/" not in lines
    for private_api in ("/api/portfolio", "/api/orders", "/api/assistant/", "/api/settings", "/api/favorites/"):
        assert f"Disallow: {private_api}" in lines
    assert "Sitemap: https://pea.example/sitemap.xml" in lines


def test_sitemap_lists_public_pages_and_all_active_securities(online, db):
    stock = make_security(db, "AB.PA", name="A&B <Group>")
    etf = make_security(db, "CW8.PA", kind="etf")
    other = make_security(db, "XX.PA", eligibility="non_eligible")
    make_security(db, "OLD.PA", active=False)
    make_security(db, "^FCHI", kind="index")
    response = online.get("/api/seo/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(response.content)
    locs = [el.text for el in root.iter(f"{SITEMAP_NS}loc")]
    assert locs == [
        "https://pea.example/",
        "https://pea.example/explorer",
        "https://pea.example/etf",
        "https://pea.example/premium",
        "https://pea.example/cgv",
        f"https://pea.example/titres/{stock.id}",
        f"https://pea.example/titres/{etf.id}",
        f"https://pea.example/titres/{other.id}",
    ]


def test_llms_txt_describes_site(online, db):
    make_security(db, "AB.PA")
    make_security(db, "CW8.PA", kind="etf")
    other = make_security(db, "XX.PA", eligibility="non_eligible")
    response = online.get("/api/seo/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    text = response.text
    assert text.startswith("# Cotalyx\n")
    for url in ("https://pea.example/", "https://pea.example/explorer", "https://pea.example/etf", "https://pea.example/sitemap.xml"):
        assert url in text
    assert "pas un conseil en investissement" in text
    assert "2 actions" in text and "1 ETF" in text
    assert "/portefeuille" not in text
    assert "PEA Radar" not in text and "éligibles au PEA" not in text


def test_premium_and_sales_terms_are_indexable(online):
    lines = online.get("/api/seo/robots.txt").text.splitlines()
    assert "Allow: /premium$" in lines and "Allow: /cgv" in lines
    assert "Disallow: /api/billing/" in lines
    sitemap = online.get("/api/seo/sitemap.xml").text
    assert "/premium</loc>" in sitemap and "/cgv</loc>" in sitemap


def test_robots_lets_robots_read_the_public_prices(online):
    lines = online.get("/api/seo/robots.txt").text.splitlines()
    assert "Allow: /api/billing/plans" in lines
    assert lines.index("Allow: /api/billing/plans") < lines.index("Disallow: /api/billing/")
