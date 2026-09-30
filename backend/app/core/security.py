"""Primitives de sécurité : mots de passe, jetons, codes. Fonctions pures, sans base ni réseau."""
import hashlib
import hmac
import ipaddress
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher()  # Argon2id, paramètres recommandés par la bibliothèque
# Vérifier contre un faux hachage quand le compte n'existe pas : même durée de réponse dans les deux cas.
_DUMMY_HASH = _hasher.hash("pas-un-vrai-mot-de-passe")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        ok = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return ok and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problem(password: str) -> str | None:
    """Message à afficher si le mot de passe est refusé, sinon None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères."
    if len(password) > PASSWORD_MAX_LENGTH:
        return f"Le mot de passe ne doit pas dépasser {PASSWORD_MAX_LENGTH} caractères."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def truncate_ip(ip: str | None) -> str | None:
    """IP réduite à son réseau (/24 ou /48) : assez pour repérer une anomalie, pas pour identifier quelqu'un."""
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


# L'ordre compte : Edge et Opera contiennent « Chrome/ », Chrome contient « Safari/ » ;
# Android contient « Linux », iOS contient « Mac OS X ».
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iPadOS"),
            ("Mac OS X", "macOS"), ("Linux", "Linux"))


def device_label(user_agent: str | None) -> str:
    ua = user_agent or ""
    browser = next((name for key, name in _BROWSERS if key in ua), "Navigateur inconnu")
    system = next((name for key, name in _SYSTEMS if key in ua), "système inconnu")
    return f"{browser} sur {system}"


def normalize_email(email: str) -> str:
    return email.strip().lower()
