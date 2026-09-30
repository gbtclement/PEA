from datetime import UTC, datetime

from app.core.config import get_settings
from app.services.auth.sessions import SESSION_COOKIE, NewSession, open_session


def sign_in(client, db, user, *, persistent: bool = True) -> NewSession:
    """Ouvre une session directement en base et la donne au client de test (cookie + en-tête CSRF)."""
    new = open_session(db, user, persistent=persistent, ip="203.0.113.5", user_agent="pytest",
                       now=datetime.now(UTC), settings=get_settings())
    client.cookies.set(SESSION_COOKIE, new.token)
    client.headers["X-CSRF-Token"] = new.csrf_token
    return new
