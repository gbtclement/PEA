"""Connexion Google (OpenID Connect, code + PKCE), faite côté serveur : le navigateur ne voit jamais les jetons Google."""
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]


class GoogleError(Exception):
    """Échange ou jeton d'identité refusé."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    first_name: str
    last_name: str


class GoogleClient(Protocol):
    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str: ...

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity: ...


class GoogleOIDC:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id, self.client_secret = client_id, client_secret

    def authorize_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str) -> str:
        return AUTHORIZE_URL + "?" + urlencode({
            "client_id": self.client_id, "response_type": "code", "scope": "openid email profile",
            "redirect_uri": redirect_uri, "state": state, "nonce": nonce, "code_challenge": code_challenge,
            "code_challenge_method": "S256", "prompt": "select_account",
        })

    def identify(self, *, code: str, code_verifier: str, nonce: str, redirect_uri: str) -> GoogleIdentity:
        try:
            token = httpx.post(TOKEN_URL, data={
                "code": code, "client_id": self.client_id, "client_secret": self.client_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code", "code_verifier": code_verifier,
            }, timeout=10.0)
            token.raise_for_status()
            keys = KeySet.import_key_set(httpx.get(JWKS_URL, timeout=10.0).json())
            claims = jwt.decode(token.json()["id_token"], keys, algorithms=["RS256"]).claims
            jwt.JWTClaimsRegistry(
                leeway=60,
                iss={"essential": True, "values": ISSUERS},
                aud={"essential": True, "value": self.client_id},
                nonce={"essential": True, "value": nonce},
                sub={"essential": True},
                exp={"essential": True},
            ).validate(claims)
        except (httpx.HTTPError, KeyError, ValueError, JoseError) as error:
            raise GoogleError(str(error)) from error
        return GoogleIdentity(sub=str(claims["sub"]), email=str(claims.get("email", "")).lower(),
                              email_verified=bool(claims.get("email_verified")),
                              first_name=str(claims.get("given_name", ""))[:100],
                              last_name=str(claims.get("family_name", ""))[:100])
