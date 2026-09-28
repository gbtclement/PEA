import hashlib

import httpx

from app.services.auth.breach import HibpChecker, suffix_found

FORM = {"first_name": "Jean", "last_name": "Dupont", "email": "jean@example.com",
        "password": "motdepasse123", "accept_terms": True}


def test_suffix_found_reads_the_range_answer():
    body = "0018A45C4D1DEF81644B54AB7F969B88D65:3\r\n00D4F6E8FA6EECAD2A3AA415EEC418D38EC:0\r\n"
    assert suffix_found(body, "0018a45c4d1def81644b54ab7f969b88d65")
    assert not suffix_found(body, "00D4F6E8FA6EECAD2A3AA415EEC418D38EC")  # 0 = remplissage (Add-Padding)
    assert not suffix_found(body, "FFFF")


def test_only_the_first_five_characters_leave_the_server(monkeypatch):
    sha1 = hashlib.sha1(b"motdepasse123").hexdigest().upper()
    seen = []

    def fake_get(url, headers, timeout):
        seen.append((url, headers, timeout))
        return httpx.Response(200, text=f"{sha1[5:]}:42\r\n", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    assert HibpChecker().is_pwned("motdepasse123")
    assert seen[0][0].endswith(f"/range/{sha1[:5]}") and seen[0][2] == 2.0 and seen[0][1]["Add-Padding"] == "true"


def test_a_silent_service_is_ignored(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectTimeout("trop long")

    monkeypatch.setattr(httpx, "get", boom)
    assert not HibpChecker().is_pwned("motdepasse123")


def test_signup_and_reset_refuse_a_pwned_password(anon_client, fake_breach):
    fake_breach.pwned.add("motdepasse123")
    refused = anon_client.post("/api/auth/register", json=FORM)
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "pwned_password"
    reset = anon_client.post("/api/auth/reset-password", json={"token": "x" * 43, "password": "motdepasse123"})
    assert reset.json()["detail"]["code"] == "pwned_password"
