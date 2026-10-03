"""En-têtes de cache (bloc F) : réponses publiques réutilisables, jamais celles d'un membre connecté."""
from tests.factories import make_quote, make_security


def test_public_answer_is_cacheable_with_etag(anon_client, db):
    make_quote(db, make_security(db, "MC.PA", name="LVMH"), 600.0)
    response = anon_client.get("/api/screener", params={"kind": "stock"})
    assert response.headers["cache-control"] == "public, max-age=60"
    assert "Cookie" in response.headers["vary"]
    assert response.headers["etag"].startswith('W/"')


def test_if_none_match_gives_304(anon_client, db):
    make_quote(db, make_security(db, "MC.PA", name="LVMH"), 600.0)
    first = anon_client.get("/api/rankings/top")
    again = anon_client.get("/api/rankings/top", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b""


def test_public_api_private_with_session(client, db):
    # Favoris, enveloppes : la réponse d'un membre ne doit être gardée par aucun intermédiaire.
    response = client.get("/api/rankings/top")
    assert response.headers["cache-control"] == "private, no-store"
    assert "etag" not in response.headers


def test_personal_routes_never_public(client):
    for path in ("/api/me", "/api/portfolio"):
        assert "public" not in client.get(path).headers.get("cache-control", "")


def test_seo_files_are_cacheable(anon_client):
    assert anon_client.get("/api/seo/robots.txt").headers["cache-control"] == "public, max-age=3600"
    assert anon_client.get("/api/seo/sitemap.xml").headers["cache-control"] == "public, max-age=3600"
