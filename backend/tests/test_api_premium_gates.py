from tests.factories import make_security, make_subscription


def test_free_member_gets_403_on_reserved_forecasts(client, db):
    security = make_security(db, "MC.PA")
    for path in ("/api/forecasts", f"/api/securities/{security.id}/forecast"):
        response = client.get(path)
        assert response.status_code == 403, path
        assert response.json()["detail"]["code"] == "premium_required"


def test_free_member_keeps_the_track_record(client):
    assert client.get("/api/forecasts/signals").status_code == 200
    assert client.get("/api/forecasts/track-record").status_code == 200


def test_subscriber_and_offered_member_see_forecasts(client, db, user):
    make_subscription(db, user)
    db.refresh(user)
    assert client.get("/api/forecasts").status_code == 200
    user.subscription.status = "canceled"
    user.is_premium = True
    db.flush()
    assert client.get("/api/forecasts").status_code == 200
