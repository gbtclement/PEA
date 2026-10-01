"""Jeton des liens de désinscription : signé avec APP_SECRET, jamais stocké (Ruling 1 du plan)."""
import base64
import hashlib
import hmac
import uuid


def make_token(user_id: uuid.UUID, secret: str) -> str:
    if not secret:
        raise ValueError("APP_SECRET manquant : impossible de signer un lien de désinscription")
    mac = hmac.new(secret.encode(), f"unsubscribe:{user_id}".encode(), hashlib.sha256).digest()
    return f"{user_id.hex}.{base64.urlsafe_b64encode(mac[:16]).decode().rstrip('=')}"


def read_token(token: str | None, secret: str) -> uuid.UUID | None:
    """Le compte visé si la signature est bonne, sinon None."""
    if not secret or not token or "." not in token:
        return None
    raw_id = token.split(".", 1)[0]
    try:
        user_id = uuid.UUID(hex=raw_id)
    except ValueError:
        return None
    return user_id if hmac.compare_digest(make_token(user_id, secret), token) else None
