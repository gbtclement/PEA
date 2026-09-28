import asyncio
import json
import threading
from contextlib import nullcontext
from types import SimpleNamespace

from app.models import ChatMessage, Conversation
from app.services.assistant.catalog import get_model
from app.services.assistant.chat import ChatRun
from app.services.assistant.streaming import sse_events, start_chat


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
