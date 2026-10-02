import logging
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_llm_factory, get_session_maker
from app.api.routes.orders import paris_today
from app.core.config import get_settings
from app.core.current_user import get_current_user, get_now, require_premium
from app.core.db import get_db
from app.models import ChatMessage, Conversation, Security, User
from app.repositories.app_settings import get_app_settings
from app.repositories.assistant import (
    DEFAULT_TITLE, claude_history, conversation_messages, conversation_out, message_out, owned_conversation,
)
from app.repositories.user_settings import get_user_settings
from app.schemas.assistant import AssistantStatusOut, ConversationDetail, ConversationIn, ConversationOut, MessageIn
from app.services.assistant.catalog import get_model
from app.services.assistant.chat import ChatRun
from app.services.assistant.prompt import system_prompt
from app.services.assistant.streaming import SessionMaker, sse_events, start_chat
from app.services.assistant.usage import month_spent

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)


def _status(db: Session, user: User, now: datetime) -> AssistantStatusOut:
    app_settings = get_app_settings(db)
    spent, limit = month_spent(db, user.id, now), app_settings.ai_monthly_cost_limit_usd
    reason = None
    if not user.has_premium:
        reason = "premium"
    elif not get_settings().anthropic_api_key:
        reason = "not_configured"
    elif spent >= limit:
        reason = "limit_reached"
    return AssistantStatusOut(available=reason is None, reason=reason, spent_usd=round(spent, 4), limit_usd=limit,
                              model=get_model(app_settings.ai_model).label)


@router.get("/assistant/status", response_model=AssistantStatusOut)
def assistant_status(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                     now: datetime = Depends(get_now)) -> AssistantStatusOut:
    return _status(db, user, now)


@router.get("/assistant/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(require_premium)) -> list[ConversationOut]:
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.updated_at.desc(), Conversation.id.desc()))
    return [conversation_out(db, c) for c in rows]


@router.post("/assistant/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationIn, db: Session = Depends(get_db), user: User = Depends(require_premium)) -> ConversationOut:
    title = DEFAULT_TITLE
    if payload.security_id is not None:
        security = db.get(Security, payload.security_id)
        if security is None:
            raise HTTPException(status_code=404, detail="Titre introuvable")
        title = f"À propos de {security.name}"[:120]
    conv = Conversation(user_id=user.id, title=title, security_id=payload.security_id)
    db.add(conv)
    db.commit()
    return conversation_out(db, conv)


@router.get("/assistant/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(require_premium)) -> ConversationDetail:
    conv = owned_conversation(db, user.id, conversation_id)
    return ConversationDetail(**conversation_out(db, conv).model_dump(),
                              messages=[message_out(m) for m in conversation_messages(db, conv.id)])


@router.delete("/assistant/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(require_premium)) -> None:
    db.delete(owned_conversation(db, user.id, conversation_id))
    db.commit()

@router.post("/assistant/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(require_premium),
    llm_factory: Callable = Depends(get_llm_factory), session_maker: SessionMaker = Depends(get_session_maker),
    now: datetime = Depends(get_now),
) -> StreamingResponse:
    conv = owned_conversation(db, user.id, conversation_id)
    row = get_user_settings(db, user.id)
    status = _status(db, user, now)
    if status.reason == "not_configured":
        raise HTTPException(409, detail={"code": "ai_not_configured",
                                         "message": "L'assistant n'est pas encore configuré (ANTHROPIC_API_KEY)."})
    if status.reason == "limit_reached":
        raise HTTPException(429, detail={"code": "ai_limit_reached", "message": (
            f"Limite mensuelle de l'assistant atteinte ({status.limit_usd:.2f} $) : elle repart le 1er du mois.")})
    config = get_settings()
    api_key = config.anthropic_api_key
    model = get_model(get_app_settings(db).ai_model)
    security = db.get(Security, conv.security_id) if conv.security_id else None
    history = claude_history([*conversation_messages(db, conv.id), ChatMessage(role="user", content=payload.content)])
    user_msg = ChatMessage(conversation_id=conv.id, role="user", content=payload.content, tools=[])
    db.add(user_msg)
    if conv.title == DEFAULT_TITLE:
        conv.title = payload.content[:60] + ("…" if len(payload.content) > 60 else "")
    conv.updated_at = func.now()
    db.commit()
    start = {"type": "start", "user_message": message_out(user_msg).model_dump(mode="json")}
    run = ChatRun(llm_factory(api_key), model=model,
                  system=system_prompt(paris_today(), row.min_orders_per_year, row.envelopes or [], security),
                  history=history, execute_tool=None,
                  max_tokens=config.assistant_max_tokens, max_rounds=config.assistant_max_rounds)
    chat = start_chat(run, session_maker, conv.id, user.id, model)
    return StreamingResponse(sse_events(start, chat), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
