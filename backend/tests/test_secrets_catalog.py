from types import SimpleNamespace

import pytest

from app.services.assistant.catalog import MODELS, Usage, estimate_cost, get_model
from app.services.secrets import MissingSecretError, decrypt_secret, encrypt_secret


def test_encrypt_roundtrip_and_ciphertext_differs():
    token = encrypt_secret("sk-ant-abc", "secret-1")
    assert token != "sk-ant-abc" and "sk-ant" not in token
    assert decrypt_secret(token, "secret-1") == "sk-ant-abc"


def test_decrypt_with_other_secret_returns_none():
    assert decrypt_secret(encrypt_secret("sk-ant-abc", "secret-1"), "secret-2") is None


def test_encrypt_without_secret_raises():
    with pytest.raises(MissingSecretError):
        encrypt_secret("sk-ant-abc", "")


def test_get_model_defaults_to_opus_5():
    assert get_model(None).id == "claude-opus-5"
    assert get_model("inconnu").id == "claude-opus-5"
    assert get_model("claude-sonnet-5").id == "claude-sonnet-5"
    assert get_model("claude-opus-5").fallback == "default"
    assert not get_model("claude-haiku-4-5").adaptive_thinking
    assert {m.id for m in MODELS} >= {"claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"}


def test_usage_add_and_cost():
    usage = Usage()
    usage.add(SimpleNamespace(input_tokens=1000, output_tokens=2000, cache_read_input_tokens=None,
                              cache_creation_input_tokens=0, server_tool_use=SimpleNamespace(web_search_requests=2)))
    usage.add(SimpleNamespace(input_tokens=1000, output_tokens=0))
    assert (usage.input_tokens, usage.output_tokens, usage.web_searches) == (2000, 2000, 2)
    # Opus 5 : 5 $/Mtok en entrée, 25 $/Mtok en sortie, 0,01 $ par recherche
    assert estimate_cost(get_model("claude-opus-5"), usage) == pytest.approx(0.002 * 5 + 0.002 * 25 + 0.02)
