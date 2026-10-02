from app.models import UserSettings
from app.repositories.user_envelopes import user_envelopes
from tests.factories import make_score, make_security


def _choose(db, user, envelopes):
    db.merge(UserSettings(user_id=user.id, envelopes=envelopes))
    db.flush()


def test_envelopes_default_to_empty_and_are_saved(client, db, user):
    assert client.get("/api/settings/envelopes").json() == {"envelopes": []}
    body = client.put("/api/settings/envelopes", json={"envelopes": ["pea_pme", "pea", "pea"]}).json()
    assert body == {"envelopes": ["pea", "pea_pme"]}  # dédoublonné, dans l'ordre du registre
    assert user_envelopes(db, user.id) == ["pea", "pea_pme"]
    assert client.get("/api/settings/envelopes").json() == {"envelopes": ["pea", "pea_pme"]}


def test_envelopes_reject_unknown_codes(client, user):
    assert client.put("/api/settings/envelopes", json={"envelopes": ["livret_a"]}).status_code == 422


def test_envelopes_need_an_account(anon_client):
    assert anon_client.get("/api/settings/envelopes").status_code == 401


def test_saving_fees_keeps_envelopes(client, db, user):
    client.put("/api/settings/envelopes", json={"envelopes": ["pea"]})
    client.put("/api/settings", json={"min_orders_per_year": 10, "penalty_fee": 50, "fee_grid": [{"up_to": None, "rate": 0.001}]})
    assert user_envelopes(db, user.id) == ["pea"]


def _top_universe(db):
    foreign = make_security(db, "AAPL.PA", name="Apple", eligibility="non_eligible", country="US")
    pea = make_security(db, "MC.PA", name="LVMH")
    pme = make_security(db, "ALCAR.PA", name="Carmat", pea_pme="eligible")
    unsure = make_security(db, "GFC.PA", name="Gecina", eligibility="a_verifier")
    for security, total in ((foreign, 95), (pea, 90), (pme, 80), (unsure, 70)):
        make_score(db, security, total=total)
    return foreign, pea, pme, unsure


def _top_names(client):
    return [item["name"] for item in client.get("/api/rankings/top").json()]


def test_visitor_sees_every_security_in_the_top(anon_client, db):
    _top_universe(db)
    assert _top_names(anon_client) == ["Apple", "LVMH", "Carmat", "Gecina"]


def test_top_follows_the_user_envelopes(client, db, user):
    _top_universe(db)
    assert _top_names(client) == ["Apple", "LVMH", "Carmat", "Gecina"]  # rien de choisi : tout
    _choose(db, user, ["pea"])
    assert _top_names(client) == ["LVMH", "Carmat"]  # « à vérifier » exclu
    _choose(db, user, ["pea_pme"])
    assert _top_names(client) == ["Carmat"]
    _choose(db, user, ["pea", "cto"])
    assert _top_names(client) == ["Apple", "LVMH", "Carmat", "Gecina"]  # le compte-titres accepte tout


def test_manual_correction_leaves_the_pea_top_at_once(client, db, user, admin_client):
    _, pea, _, _ = _top_universe(db)
    _choose(db, user, ["pea"])
    admin_client.patch(f"/api/securities/{pea.id}/eligibility", json={"override": "non_eligible"})
    assert "LVMH" not in _top_names(client)


def test_movers_and_heatmap_follow_the_envelopes(client, db, user):
    from tests.factories import make_quote
    foreign, pea, _, _ = _top_universe(db)
    make_quote(db, foreign, 100.0, change_pct=5.0)
    make_quote(db, pea, 100.0, change_pct=-2.0)
    _choose(db, user, ["pea"])
    movers = client.get("/api/rankings/movers").json()
    assert [m["name"] for m in movers["gainers"] + movers["losers"]] == ["LVMH", "LVMH"]
