from app.core.security import (
    device_label, hash_password, needs_rehash, new_code, new_token, normalize_email, password_problem, same,
    token_hash, truncate_ip, verify_password,
)


def test_password_hash_roundtrip():
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "correct horse battery")
    assert not verify_password(stored, "wrong horse battery")
    assert not needs_rehash(stored)


def test_verify_password_without_hash_is_false():
    # compte sans mot de passe (Google, ou admin repris) : jamais de connexion par mot de passe
    assert not verify_password(None, "n'importe quoi")


def test_password_rules():
    assert password_problem("court") == "Le mot de passe doit contenir au moins 12 caractères."
    assert password_problem("x" * 129) == "Le mot de passe ne doit pas dépasser 128 caractères."
    assert password_problem("douze-lettres") is None


def test_tokens_and_codes():
    assert len(new_token()) >= 43 and new_token() != new_token()
    assert len(token_hash("abc")) == 64 and token_hash("abc") == token_hash("abc")
    codes = {new_code() for _ in range(50)}
    assert all(len(c) == 6 and c.isdigit() for c in codes) and len(codes) > 1
    assert same("abc", "abc") and not same("abc", "abd")


def test_truncate_ip():
    assert truncate_ip("203.0.113.57") == "203.0.113.0/24"
    assert truncate_ip("2001:db8:1234:5678::1") == "2001:db8:1234::/48"
    assert truncate_ip("pas une ip") is None
    assert truncate_ip(None) is None


def test_device_label():
    chrome_windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    safari_iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
    firefox_android = "Mozilla/5.0 (Android 15; Mobile; rv:140.0) Gecko/140.0 Firefox/140.0"
    assert device_label(chrome_windows) == "Chrome sur Windows"
    assert device_label(safari_iphone) == "Safari sur iOS"
    assert device_label(firefox_android) == "Firefox sur Android"
    assert device_label(None) == "Navigateur inconnu sur système inconnu"


def test_normalize_email():
    assert normalize_email("  Jean.Dupont@Example.COM ") == "jean.dupont@example.com"
