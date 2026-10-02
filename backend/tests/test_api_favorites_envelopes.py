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


def _pea(body):
    return next(e for e in body["envelopes"] if e["code"] == "pea")


def test_override_and_reset_an_envelope(admin_client, db):
    security = make_security(db, "GFC.PA", eligibility="a_verifier")
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": "eligible"}).json()
    assert _pea(body) == {"code": "pea", "status": "eligible", "source": "manual", "override": "eligible"}
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": None}).json()
    assert _pea(body)["source"] == "auto" and _pea(body)["override"] is None
    assert [e["code"] for e in body["envelopes"]] == ["pea", "pea_pme"]


def test_pea_pme_can_be_corrected_on_its_own(admin_client, db):
    security = make_security(db, "ALCAR.PA")
    body = admin_client.patch(f"/api/securities/{security.id}/envelopes/pea_pme", json={"override": "eligible"}).json()
    assert {e["code"]: e["status"] for e in body["envelopes"]} == {"pea": "eligible", "pea_pme": "eligible"}


def test_envelope_override_validation(admin_client, db):
    security = make_security(db, "GFC.PA")
    assert admin_client.patch(f"/api/securities/{security.id}/envelopes/pea", json={"override": "peut-être"}).status_code == 422
    assert admin_client.patch(f"/api/securities/{security.id}/envelopes/cto", json={"override": None}).status_code == 422
    assert admin_client.patch("/api/securities/999999/envelopes/pea", json={"override": None}).status_code == 404
    assert admin_client.patch(f"/api/securities/{security.id}/eligibility", json={"override": None}).status_code in (404, 405)


def test_override_on_etf_resets_to_seed(admin_client, db):
    etf = make_security(db, "CW8.PA", kind="etf")
    admin_client.patch(f"/api/securities/{etf.id}/envelopes/pea", json={"override": "non_eligible"})
    body = admin_client.patch(f"/api/securities/{etf.id}/envelopes/pea", json={"override": None}).json()
    assert (_pea(body)["status"], _pea(body)["source"]) == ("eligible", "seed")


def test_list_overridden_only(admin_client, db):
    a = make_security(db, "A.PA")
    make_security(db, "B.PA")
    admin_client.patch(f"/api/securities/{a.id}/envelopes/pea", json={"override": "non_eligible"})
    items = admin_client.get("/api/securities", params={"overridden": "true"}).json()["items"]
    assert [i["symbol"] for i in items] == ["A"]
