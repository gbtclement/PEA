"""Have I Been Pwned, en k-anonymat : seuls les 5 premiers caractères du SHA-1 quittent le serveur."""
import hashlib
import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)
RANGE_URL = "https://api.pwnedpasswords.com/range/"


class BreachChecker(Protocol):
    def is_pwned(self, password: str) -> bool: ...


class NoBreachCheck:
    def is_pwned(self, password: str) -> bool:
        return False


def suffix_found(body: str, suffix: str) -> bool:
    """Vrai si le suffixe figure dans la réponse avec au moins une fuite (les lignes à 0 sont du remplissage)."""
    wanted = suffix.upper()
    for line in body.splitlines():
        candidate, _, count = line.strip().partition(":")
        if candidate.upper() == wanted and count.strip().isdigit() and int(count) > 0:
            return True
    return False


class HibpChecker:
    def is_pwned(self, password: str) -> bool:
        digest = hashlib.sha1(password.encode()).hexdigest().upper()
        try:
            response = httpx.get(RANGE_URL + digest[:5], headers={"Add-Padding": "true"}, timeout=2.0)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Have I Been Pwned ne répond pas : vérification ignorée")
            return False
        return suffix_found(response.text, digest[5:])
