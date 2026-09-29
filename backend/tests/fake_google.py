from urllib.parse import urlencode

from app.services.auth.google import GoogleError, GoogleIdentity


class FakeGoogle:
    """Remplace Google : `identity` est le compte « choisi » par l'utilisateur ; seul le code « bon-code » passe."""

    def __init__(self) -> None:
        self.identity = GoogleIdentity(sub="google-123", email="jean@gmail.com", email_verified=True,
                                       first_name="Jean", last_name="Dupont")
        self.last_nonce: str | None = None
        self.last_verifier: str | None = None

    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str:
        return "https://accounts.google.test/auth?" + urlencode({"state": state, "nonce": nonce,
                                                                  "code_challenge": code_challenge})

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity:
        if code != "bon-code":
            raise GoogleError("code refusé")
        self.last_nonce, self.last_verifier = nonce, code_verifier
        return self.identity
