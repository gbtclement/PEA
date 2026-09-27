import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class MissingSecretError(Exception):
    """APP_SECRET absent : impossible de chiffrer une clé en base."""


def _fernet(secret: str) -> Fernet:
    if not secret:
        raise MissingSecretError
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def encrypt_secret(plain: str, secret: str) -> str:
    return _fernet(secret).encrypt(plain.encode()).decode()


def decrypt_secret(token: str, secret: str) -> str | None:
    try:
        return _fernet(secret).decrypt(token.encode()).decode()
    except (InvalidToken, MissingSecretError):
        return None
