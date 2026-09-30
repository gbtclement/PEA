from app.models import Favorite, SecurityScore
from tests.factories import make_score, make_security


def test_score_roundtrip(db):
    security = make_security(db, "MC.PA")
    make_score(db, security, total=72.5, components=[{"key": "trend", "points": 20}], sparkline=[1.0, 2.0])
    stored = db.get(SecurityScore, security.id)
    assert stored.total == 72.5
    assert stored.components[0]["key"] == "trend"
    assert stored.sparkline == [1.0, 2.0]


def test_favorite_roundtrip(db, user):
    security = make_security(db, "MC.PA")
    db.add(Favorite(user_id=user.id, security_id=security.id))
    db.flush()
    assert db.get(Favorite, (user.id, security.id)) is not None
