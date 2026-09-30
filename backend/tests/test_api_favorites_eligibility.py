from app.models import Favorite
from tests.factories import make_security


def test_add_and_remove_favorite(client, db, user):
    security = make_security(db, "MC.PA")
    assert client.put(f"/api/favorites/{security.id}").status_code == 204
    assert client.put(f"/api/favorites/{security.id}").status_code == 204  # idempotent
    assert db.get(Favorite, (user.id, security.id)) is not None
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert client.delete(f"/api/favorites/{security.id}").status_code == 204
    assert db.get(Favorite, (user.id, security.id)) is None


def test_favorite_unknown_security(client):
    assert client.put("/api/favorites/999999").status_code == 404


def test_override_and_reset_eligibility(admin_client, db):
    security = make_security(db, "GFC.PA")
    security.industry = "REIT - Office"
    db.flush()
    body = admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "eligible"}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("eligible", "override", "eligible")
    body = admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"], body["eligibility_override"]) == ("a_verifier", "auto", None)


def test_override_on_etf_resets_to_seed(admin_client, db):
    etf = make_security(db, "CW8.PA", kind="etf")
    admin_client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": "non_eligible"})
    body = admin_client.patch(f"/api/securities/{etf.id}/eligibility", json={"override": None}).json()
    assert (body["eligibility"], body["eligibility_source"]) == ("eligible", "seed")


def test_override_validation(admin_client, db):
    security = make_security(db, "MC.PA")
    assert admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": "peut-être"}).status_code == 422
    assert admin_client.patch("/api/securities/999999/eligibility", json={"override": None}).status_code == 404


def test_list_overridden_only(admin_client, db):
    a = make_security(db, "A.PA")
    make_security(db, "B.PA")
    admin_client.patch(f"/api/securities/{a.id}/eligibility", json={"override": "non_eligible"})
    items = admin_client.get("/api/securities", params={"overridden": "true"}).json()["items"]
    assert [i["symbol"] for i in items] == ["A"]
