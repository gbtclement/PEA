from app.core.current_user import ensure_default_user
from app.models import UserSettings


def test_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert body == {"min_orders_per_year": 12, "penalty_fee": 96.0, "fee_grid": [
        {"up_to": 500.0, "rate": 0.0048}, {"up_to": 1000.0, "rate": 0.0018}, {"up_to": None, "rate": 0.0012}]}


def test_settings_update_and_fee_estimate_uses_grid(client, db):
    payload = {"min_orders_per_year": 10, "penalty_fee": 80, "fee_grid": [{"up_to": 1000, "rate": 0.01}, {"up_to": None, "rate": 0.005}]}
    assert client.put("/api/settings", json=payload).status_code == 200
    user = ensure_default_user(db)
    assert db.get(UserSettings, user.id).min_orders_per_year == 10
    assert client.get("/api/fees/estimate", params={"amount": 800}).json() == {"amount": 800.0, "fee": 8.0, "rate": 0.01}


def test_settings_rejects_invalid_grid(client):
    base = {"min_orders_per_year": 12, "penalty_fee": 96}
    for grid in (
        [{"up_to": 1000, "rate": 0.01}, {"up_to": 500, "rate": 0.005}, {"up_to": None, "rate": 0.001}],  # bornes décroissantes
        [{"up_to": None, "rate": 0.2}],                                                                 # taux > 5 %
        [{"up_to": 500, "rate": 0.01}],                                                                 # dernière tranche bornée
        [{"up_to": None, "rate": 0.01}, {"up_to": None, "rate": 0.01}],                                 # tranche illimitée au milieu
        [],
    ):
        assert client.put("/api/settings", json={**base, "fee_grid": grid}).status_code == 422, grid
    assert client.put("/api/settings", json={**base, "min_orders_per_year": -1, "fee_grid": [{"up_to": None, "rate": 0.01}]}).status_code == 422
