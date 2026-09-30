from app.models import ChatMessage, Conversation
from app.repositories.assistant import claude_history
from tests.factories import make_security, make_user


def test_create_list_get_delete_conversation(client, db):
    s = make_security(db, "MC.PA", name="LVMH")
    created = client.post("/api/assistant/conversations", json={"security_id": s.id})
    assert created.status_code == 201
    conv = created.json()
    assert (conv["title"], conv["security_name"], conv["security_symbol"], conv["cost_usd"]) == ("À propos de LVMH", "LVMH", "MC", 0)
    plain = client.post("/api/assistant/conversations", json={}).json()
    assert plain["title"] == "Nouvelle conversation" and plain["security_id"] is None
    assert [c["id"] for c in client.get("/api/assistant/conversations").json()] == [plain["id"], conv["id"]]
    detail = client.get(f"/api/assistant/conversations/{conv['id']}").json()
    assert detail["messages"] == []
    assert client.delete(f"/api/assistant/conversations/{conv['id']}").status_code == 204
    assert client.get(f"/api/assistant/conversations/{conv['id']}").status_code == 404


def test_unknown_security_is_404(client):
    assert client.post("/api/assistant/conversations", json={"security_id": 999999}).status_code == 404


def test_other_user_conversation_is_404(client, db):
    other = make_user(db, "autre@example.com")
    conv = Conversation(user_id=other.id, title="Secret")
    db.add(conv)
    db.flush()
    assert client.get(f"/api/assistant/conversations/{conv.id}").status_code == 404
    assert client.delete(f"/api/assistant/conversations/{conv.id}").status_code == 404
    assert client.post(f"/api/assistant/conversations/{conv.id}/messages", json={"content": "Bonjour"}).status_code == 404
    assert all(c["id"] != conv.id for c in client.get("/api/assistant/conversations").json())


def test_history_skips_empty_and_merges_consecutive_user_messages():
    messages = [
        ChatMessage(role="user", content="Bonjour"),
        ChatMessage(role="assistant", content="", interrupted=True, error="Service indisponible"),
        ChatMessage(role="user", content="Tu es là ?"),
        ChatMessage(role="assistant", content="Oui."),
    ]
    assert claude_history(messages) == [
        {"role": "user", "content": "Bonjour\n\nTu es là ?"},
        {"role": "assistant", "content": "Oui."},
    ]
