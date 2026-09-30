"""Exécution d'une réponse de l'assistant dans un fil dédié, relayée au navigateur en SSE.

Le fil a sa propre session : il enregistre toujours la réponse (complète ou partielle), même si le
navigateur part en cours de route. Le flux SSE est un générateur asynchrone : Starlette l'annule dès
la déconnexion, ce qui prévient le fil, qui ferme alors la connexion à Claude et enregistre.
"""
import json
import logging
import queue
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

import anyio.to_thread
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ChatMessage, Conversation, User
from app.repositories.assistant import conversation_out, message_out
from app.services.assistant.catalog import AssistantModel, estimate_cost
from app.services.assistant.usage import add_cost
from app.services.assistant.chat import ChatRun
from app.services.assistant.tools import ToolError, run_tool

logger = logging.getLogger(__name__)
SessionMaker = Callable[[], AbstractContextManager[Session]]
_END = object()


def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def tool_executor(db: Session, user: User) -> Callable[[str, dict, str], dict]:
    def execute(name: str, tool_input: dict, tool_use_id: str) -> dict:
        try:
            content = json.dumps(run_tool(db, user, name, tool_input), ensure_ascii=False, default=str)
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
        except ToolError as exc:
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": str(exc), "is_error": True}
        except Exception:
            logger.exception("Tool %s failed", name)
            db.rollback()
            return {"type": "tool_result", "tool_use_id": tool_use_id, "content": "Erreur interne de l'outil.",
                    "is_error": True}
    return execute


def save_reply(db: Session, conversation_id: int, user_id: uuid.UUID, model: AssistantModel,
               run: ChatRun) -> tuple[ChatMessage, Conversation] | None:
    """Enregistre la réponse. Renvoie None si la conversation a été supprimée pendant la réponse."""
    cost = estimate_cost(model, run.usage)
    # Le coût d'abord, et à part : supprimer la conversation en cours de réponse ne doit pas la rendre gratuite.
    add_cost(db, user_id, cost, datetime.now(UTC))
    db.commit()
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        return None
    msg = ChatMessage(conversation_id=conversation_id, role="assistant", content=run.text,
                      tools=list(dict.fromkeys(run.tools)), input_tokens=run.usage.input_tokens,
                      output_tokens=run.usage.output_tokens, cost_usd=cost, model=model.id,
                      interrupted=not run.completed, error=run.error)
    db.add(msg)
    conv.input_tokens += run.usage.input_tokens
    conv.output_tokens += run.usage.output_tokens
    conv.cost_usd += cost
    conv.updated_at = func.now()
    db.commit()
    return msg, conv


@dataclass
class ChatStream:
    events: queue.Queue
    cancel: threading.Event
    thread: threading.Thread


def start_chat(run: ChatRun, session_maker: SessionMaker, conversation_id: int, user_id: uuid.UUID,
               model: AssistantModel) -> ChatStream:
    events: queue.Queue = queue.Queue()

    def work() -> None:
        try:
            with session_maker() as db:
                try:
                    run.execute_tool = tool_executor(db, db.get(User, user_id))
                    for event in run.events():
                        events.put(sse(event))
                    if run.error:
                        events.put(sse({"type": "error", "message": run.error}))
                finally:
                    saved = save_reply(db, conversation_id, user_id, model, run)
                    if saved is None:
                        events.put(sse({"type": "error", "message": "La conversation a été supprimée pendant la réponse."}))
                    else:
                        msg, conv = saved
                        events.put(sse({"type": "done", "message": message_out(msg).model_dump(mode="json"),
                                        "conversation": conversation_out(db, conv).model_dump(mode="json")}))
        except Exception:
            logger.exception("Assistant reply could not be saved")
            events.put(sse({"type": "error", "message": "Impossible d'enregistrer la réponse."}))
        finally:
            events.put(_END)

    thread = threading.Thread(target=work, name=f"assistant-{conversation_id}", daemon=True)
    thread.start()
    return ChatStream(events=events, cancel=run.cancel, thread=thread)


async def sse_events(start: dict, chat: ChatStream) -> AsyncIterator[str]:
    try:
        yield sse(start)
        while (item := await anyio.to_thread.run_sync(chat.events.get, abandon_on_cancel=True)) is not _END:
            yield item
    finally:
        chat.cancel.set()  # navigateur parti (ou flux terminé) : le fil arrête Claude et enregistre
