import base64
import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import RSAKey

from app.core.security import _b64, pkce_challenge, sign, unsign
from app.services.auth.google import GoogleError, GoogleOIDC

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_signed_value_round_trip_and_tampering():
    value = sign({"state": "abc"}, "secret", NOW)
    assert unsign(value, "secret", NOW + timedelta(minutes=5), timedelta(minutes=10)) == {"state": "abc"}
    assert unsign(value, "autre", NOW, timedelta(minutes=10)) is None
    assert unsign(value + "x", "secret", NOW, timedelta(minutes=10)) is None
    assert unsign(value, "secret", NOW + timedelta(minutes=11), timedelta(minutes=10)) is None
    assert unsign(None, "secret", NOW, timedelta(minutes=10)) is None


def test_pkce_challenge_is_s256():
    expected = base64.urlsafe_b64encode(hashlib.sha256(b"verifier").digest()).rstrip(b"=").decode()
    assert pkce_challenge("verifier") == expected


def test_authorize_url_asks_for_pkce_and_openid():
    url = GoogleOIDC("id-client", "secret").authorize_url(state="s", nonce="n", code_challenge="c",
                                                          redirect_uri="http://localhost:8095/api/auth/google/callback")
    for part in ("client_id=id-client", "response_type=code", "scope=openid+email+profile", "state=s", "nonce=n",
                 "code_challenge=c", "code_challenge_method=S256"):
        assert part in url


@pytest.fixture
def signing_key():
    return RSAKey.generate_key(2048, parameters={"kid": "k1"})


def _id_token(key, **claims):
    base = {"iss": "https://accounts.google.com", "aud": "id-client", "sub": "123", "email": "jean@gmail.com",
            "email_verified": True, "given_name": "Jean", "family_name": "Dupont", "nonce": "n",
            "iat": int(time.time()), "exp": int(time.time()) + 600}
    return jwt.encode({"alg": "RS256", "kid": "k1"}, {**base, **claims}, key)


def _mock_google(monkeypatch, key, token):
    monkeypatch.setattr(httpx, "post", lambda url, data, timeout: httpx.Response(
        200, json={"id_token": token}, request=httpx.Request("POST", url)))
    monkeypatch.setattr(httpx, "get", lambda url, timeout: httpx.Response(
        200, json={"keys": [key.as_dict(private=False)]}, request=httpx.Request("GET", url)))


def test_identify_checks_signature_audience_and_nonce(monkeypatch, signing_key):
    _mock_google(monkeypatch, signing_key, _id_token(signing_key))
    identity = GoogleOIDC("id-client", "secret").identify(code="c", code_verifier="v", nonce="n", redirect_uri="r")
    assert (identity.sub, identity.email, identity.email_verified, identity.first_name) == ("123", "jean@gmail.com",
                                                                                            True, "Jean")


@pytest.mark.parametrize("claims", [{"aud": "autre-client"}, {"nonce": "rejoue"}, {"iss": "https://evil.example"},
                                    {"exp": int(time.time()) - 3600}])
def test_identify_refuses_a_foreign_or_replayed_token(monkeypatch, signing_key, claims):
    _mock_google(monkeypatch, signing_key, _id_token(signing_key, **claims))
    with pytest.raises(GoogleError):
        GoogleOIDC("id-client", "secret").identify(code="c", code_verifier="v", nonce="n", redirect_uri="r")


def test_an_empty_secret_never_signs_nor_verifies():
    now = datetime(2026, 9, 29, tzinfo=UTC)
    with pytest.raises(ValueError):
        sign({"sub": "x"}, "", now)
    forged = sign({"sub": "x"}, "n-importe-quoi", now).rsplit(".", 1)[0]
    empty_key_mac = _b64(hmac.new(b"", forged.encode(), hashlib.sha256).digest())
    assert unsign(f"{forged}.{empty_key_mac}", "", now, timedelta(minutes=5)) is None
