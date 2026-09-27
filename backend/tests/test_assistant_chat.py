import json

import anthropic
import httpx
import pytest

from app.core.config import get_settings
from app.models import ChatMessage
from app.services.assistant.chat import friendly_error
from tests.factories import make_security
from tests.fake_llm import error_turn, text_turn, tool_turn

KEY = "sk-ant-test-1234567890abcdef"


@pytest.fixture(autouse=True)
def configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    client.put("/api/assistant/settings", json={"api_key": KEY, "model": "claude-opus-5"})


def events(response) -> list[dict]:
    return [json.loads(line[6:]) for line in response.text.split("\n") if line.startswith("data: ")]


def new_conversation(client, **body) -> int:
    return client.post("/api/assistant/conversations", json=body).json()["id"]


def send(client, cid, content="Bonjour"):
    return client.post(f"/api/assistant/conversations/{cid}/messages", json={"content": content})


def test_streams_text_and_persists_both_messages(client, db, fake_llm):
    fake_llm.turns = [text_turn("Bon", "jour !", input_tokens=1000, output_tokens=2000)]
    cid = new_conversation(client)
    response = send(client, cid, "Salut, qui es-tu ?")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
    evts = events(response)
    assert [e["type"] for e in evts] == ["start", "text", "text", "done"]
    assert evts[0]["user_message"]["content"] == "Salut, qui es-tu ?"
    done = evts[-1]
    assert done["message"]["content"] == "Bonjour !" and done["message"]["interrupted"] is False
    assert done["message"]["cost_usd"] == pytest.approx(0.001 * 5 + 0.002 * 25, abs=1e-4)
    assert done["conversation"]["title"] == "Salut, qui es-tu ?" and done["conversation"]["output_tokens"] == 2000
    assert fake_llm.api_keys == [KEY]
    call = fake_llm.calls[0]
    assert call["model"] == "claude-opus-5" and call["thinking"] == {"type": "adaptive"}
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["extra_body"] == {"fallbacks": "default"}
    assert {"type": "web_search_20260209", "name": "web_search", "max_uses": 3} in call["tools"]
    assert "français" in call["system"] and call["messages"] == [{"role": "user", "content": "Salut, qui es-tu ?"}]
    detail = client.get(f"/api/assistant/conversations/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


def test_tool_loop_runs_tools_and_sends_results(client, db, fake_llm):
    make_security(db, "MC.PA", name="LVMH")
    fake_llm.turns = [tool_turn("get_security_overview", {"ticker": "MC.PA"}), text_turn("LVMH va bien.")]
    evts = events(send(client, new_conversation(client), "Et LVMH ?"))
    assert {"type": "tool", "name": "get_security_overview", "label": "Fiche du titre"} in evts
    second = fake_llm.calls[1]["messages"]
    result = second[-1]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1" and "LVMH" in result["content"]
    assert "is_error" not in result
    assert evts[-1]["message"]["tools"] == ["get_security_overview"]


def test_tool_error_is_sent_back_as_is_error(client, fake_llm):
    fake_llm.turns = [tool_turn("get_security_overview", {"ticker": "NOPE"}), text_turn("Introuvable.")]
    send(client, new_conversation(client))
    result = fake_llm.calls[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True and "introuvable" in result["content"]


def test_pause_turn_is_resumed(client, fake_llm):
    fake_llm.turns = [tool_turn("web_search", {"query": "LVMH"}, server=True), text_turn("Selon la presse…")]
    evts = events(send(client, new_conversation(client)))
    assert {"type": "tool", "name": "web_search", "label": "Recherche web"} in evts
    assert fake_llm.calls[1]["messages"][-1]["role"] == "assistant"
    assert evts[-1]["message"]["content"] == "Selon la presse…"


def _status_error(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message=f"Error code: {status} {KEY}", response=httpx.Response(status, request=request), body=None)


def test_api_error_mid_stream_keeps_partial_text(client, db, fake_llm):
    fake_llm.turns = [error_turn(_status_error(anthropic.InternalServerError, 529), "Début de réponse")]
    cid = new_conversation(client)
    evts = events(send(client, cid))
    assert [e["type"] for e in evts] == ["start", "text", "error", "done"]
    assert "indisponible" in evts[2]["message"]
    saved = evts[-1]["message"]
    assert saved["content"] == "Début de réponse" and saved["interrupted"] is True and "indisponible" in saved["error"]


def test_error_message_does_not_leak_key(client, fake_llm):
    fake_llm.turns = [error_turn(_status_error(anthropic.AuthenticationError, 401))]
    response = send(client, new_conversation(client))
    assert KEY not in response.text and "Clé API invalide" in response.text


@pytest.mark.parametrize("cls,status,expected", [
    (anthropic.AuthenticationError, 401, "Clé API invalide"),
    (anthropic.PermissionDeniedError, 403, "accès"),
    (anthropic.NotFoundError, 404, "Modèle"),
    (anthropic.RateLimitError, 429, "Limite"),
    (anthropic.APIStatusError, 402, "Crédit"),
    (anthropic.InternalServerError, 500, "indisponible"),
])
def test_friendly_errors(cls, status, expected):
    assert expected in friendly_error(_status_error(cls, status))


def test_friendly_error_connection():
    exc = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    assert "indisponible" in friendly_error(exc)


def test_refusal_is_explained(client, fake_llm):
    fake_llm.turns = [text_turn(stop_reason="refusal")]
    evts = events(send(client, new_conversation(client)))
    assert evts[-2]["type"] == "error" and "refusé" in evts[-2]["message"]


def test_history_and_security_context_sent(client, db, fake_llm):
    s = make_security(db, "MC.PA", name="LVMH")
    cid = new_conversation(client, security_id=s.id)
    fake_llm.turns = [text_turn("Premier."), text_turn("Second.")]
    send(client, cid, "Q1")
    send(client, cid, "Q2")
    call = fake_llm.calls[1]
    assert call["messages"] == [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "Premier."},
                                {"role": "user", "content": "Q2"}]
    assert "LVMH" in call["system"] and "MC.PA" in call["system"]
    assert client.get(f"/api/assistant/conversations/{cid}").json()["title"] == "À propos de LVMH"


def test_haiku_has_no_thinking_nor_fallback(client, fake_llm):
    client.put("/api/assistant/settings", json={"model": "claude-haiku-4-5"})
    fake_llm.turns = [text_turn("ok")]
    send(client, new_conversation(client))
    call = fake_llm.calls[0]
    assert "thinking" not in call and "betas" not in call and "extra_body" not in call
    assert {"type": "web_search_20250305", "name": "web_search", "max_uses": 3} in call["tools"]


def test_no_key_is_409(client, db, fake_llm):
    client.put("/api/assistant/settings", json={"remove_key": True, "model": "claude-opus-5"})
    response = send(client, new_conversation(client))
    assert response.status_code == 409 and "Réglages" in response.json()["detail"]
    assert db.query(ChatMessage).count() == 0


def test_round_limit_stops_with_error(client, fake_llm, monkeypatch):
    monkeypatch.setattr(get_settings(), "assistant_max_rounds", 2)
    fake_llm.turns = [tool_turn("get_top10", {}, "t1"), tool_turn("get_top10", {}, "t2")]
    evts = events(send(client, new_conversation(client)))
    assert evts[-2]["type"] == "error" and "étapes" in evts[-2]["message"]


def test_blank_message_is_422(client):
    assert send(client, new_conversation(client), "   ").status_code == 422


def test_usage_of_failed_round_is_counted(client, fake_llm):
    from types import SimpleNamespace

    turn = error_turn(_status_error(anthropic.InternalServerError, 529), "Début")
    turn["events"] = [SimpleNamespace(type="message_start", message=SimpleNamespace(usage=SimpleNamespace(input_tokens=800, output_tokens=1))),
                      *turn["events"], SimpleNamespace(type="message_delta", usage=SimpleNamespace(output_tokens=25))]
    fake_llm.turns = [turn]
    saved = events(send(client, new_conversation(client)))[-1]["message"]
    assert saved["cost_usd"] == pytest.approx(800 * 5e-6 + 25 * 25e-6, abs=1e-4)  # arrondi à 4 décimales
    assert saved["cost_usd"] > 0
