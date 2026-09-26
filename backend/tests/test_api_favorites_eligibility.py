from app.core.current_user import ensure_default_user
from app.models import Favorite
from tests.factories import make_security


def test_add_and_remove_favorite(client, db):
    security = make_security(db, "MC.PA")
    user = ensure_default_user(db)
    assert client.put(f"/api/favorites/{security.id}").status_code == 204
    assert client.put(f"/api/favorites/{security.id}").status_code == 204  # idempotent
    assert db.get(Favorite, (user.id, security.id)) is not None
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert db.get(Favorite, (user.id, security.id)) is None


def test_favorite_unknown_security(client):
    assert client.put("/api/favorites/999999").status_code == 404


def test_override_and_reset_eligibility(client, db):
    security = make_security(db, "GFC.PA")
    security.industry = "REIT - Office"
    db.flush()
    body = client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "eligible"}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("eligible", "override", "eligible")
    body = client.patch(f"/api/securities/{security.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("a_verifier", "auto", None)


def test_override_on_etf_resets_to_seed(client, db):
    etf = make_security(db, "CW8.PA", kind="etf")
    client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": "non_eligible"})
    body = client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"]) == ("eligible", "seed")


def test_override_validation(client, db):
    security = make_security(db, "MC.PA")
    assert client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "peut-être"}).status_code == 422
    assert client.patch("/api/securities/999999/eligibility", json={"override": None}).status_code == 404


def test_list_overridden_only(client, db):
    a = make_security(db, "A.PA")
    make_security(db, "B.PA")
    client.patch(f"/api/securities/{a.id}/eligibility", json={"override": "non_eligible"})
    items = client.get("/api/securities", params={"overridden": "true"}).json()["items"]
    assert [i["symbol"] for i in items] == ["A"]
