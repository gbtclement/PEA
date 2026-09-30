import asyncio
import json
import threading
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import delete

from app.models import ChatMessage, Conversation
from app.services.assistant.catalog import get_model
from app.services.assistant.chat import ChatRun
from app.services.assistant.streaming import sse_events, start_chat
from app.services.assistant.usage import month_spent


class _BlockingStream:
    """Envoie un premier morceau de texte puis attend que le navigateur parte (annulation)."""

    def __init__(self, cancel: threading.Event, closed: list):
        self.cancel, self.closed = cancel, closed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed.append(True)
        return False

    def __iter__(self):
        yield SimpleNamespace(type="message_start", message=SimpleNamespace(usage=SimpleNamespace(input_tokens=500, output_tokens=1)))
        yield SimpleNamespace(type="text", text="Début")
        yield SimpleNamespace(type="message_delta", usage=SimpleNamespace(output_tokens=40))
        self.cancel.wait(5)
        yield SimpleNamespace(type="text", text=" suite jamais affichée")


def test_disconnect_stops_claude_and_saves_partial_with_totals(db, user):
    conv = Conversation(user_id=user.id, title="Test")
    db.add(conv)
    db.commit()
    cancel, closed = threading.Event(), []
    llm = SimpleNamespace(stream=lambda **params: _BlockingStream(cancel, closed))
    run = ChatRun(llm, model=get_model("claude-opus-5"), system="s", history=[{"role": "user", "content": "Q"}],
                  execute_tool=None, max_tokens=1000, max_rounds=3, cancel=cancel)
    chat = start_chat(run, lambda: nullcontext(db), conv.id, user.id, get_model("claude-opus-5"))

    async def consume_then_leave() -> list[str]:
        stream = sse_events({"type": "start"}, chat)
        received = [await anext(stream), await anext(stream)]
        await stream.aclose()  # le navigateur ferme la connexion
        return received

    received = asyncio.run(consume_then_leave())
    assert json.loads(received[1][6:]) == {"type": "text", "text": "Début"}
    chat.thread.join(5)
    assert not chat.thread.is_alive() and closed == [True]
    saved = db.query(ChatMessage).filter_by(conversation_id=conv.id).one()
    assert saved.content == "Début" and saved.interrupted is True and saved.error == "Réponse interrompue."
    assert (saved.input_tokens, saved.output_tokens) == (500, 40)
    db.refresh(conv)
    assert conv.input_tokens == 500 and conv.cost_usd > 0


class _DeletingStream:
    """Réponse pendant laquelle la conversation est supprimée (autre onglet, ou appel direct à l'API)."""

    def __init__(self, db, conversation_id: int):
        self.db, self.conversation_id = db, conversation_id

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield SimpleNamespace(type="message_start", message=SimpleNamespace(usage=SimpleNamespace(input_tokens=500, output_tokens=1)))
        self.db.execute(delete(Conversation).where(Conversation.id == self.conversation_id))
        self.db.commit()
        yield SimpleNamespace(type="text", text="Réponse complète")
        yield SimpleNamespace(type="message_delta", usage=SimpleNamespace(output_tokens=40))


def test_deleting_the_conversation_during_the_reply_still_counts_its_cost(db, user):
    conv = Conversation(user_id=user.id, title="Test")
    db.add(conv)
    db.commit()
    llm = SimpleNamespace(stream=lambda **params: _DeletingStream(db, conv.id))
    run = ChatRun(llm, model=get_model("claude-opus-5"), system="s", history=[{"role": "user", "content": "Q"}],
                  execute_tool=None, max_tokens=1000, max_rounds=3, cancel=threading.Event())
    chat = start_chat(run, lambda: nullcontext(db), conv.id, user.id, get_model("claude-opus-5"))

    async def consume() -> list[str]:
        return [item async for item in sse_events({"type": "start"}, chat)]

    events = [json.loads(item[6:]) for item in asyncio.run(consume())]
    chat.thread.join(5)
    assert month_spent(db, user.id, datetime.now(UTC)) > 0  # sinon chaque réponse serait gratuite
    assert events[-1]["type"] == "error"
