import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CaptchaVerifier(Protocol):
    def verify(self, token: str | None, ip: str | None) -> bool: ...


class DisabledCaptcha:
    """TURNSTILE_SECRET_KEY vide (local, tests) : tout passe."""

    def verify(self, token: str | None, ip: str | None) -> bool:
        return True


class TurnstileVerifier:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def verify(self, token: str | None, ip: str | None) -> bool:
        if not token:
            return False
        try:
            response = httpx.post(SITEVERIFY_URL, data={"secret": self.secret, "response": token,
                                                        **({"remoteip": ip} if ip else {})}, timeout=5.0)
            return bool(response.json().get("success"))
        except (httpx.HTTPError, ValueError):
            # Cloudflare injoignable : on laisse passer plutôt que bloquer tout le monde (les limites restent actives).
            logger.warning("Turnstile injoignable : vérification ignorée")
            return True
