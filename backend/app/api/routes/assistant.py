import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_llm_factory, get_session_maker
from app.api.routes.orders import paris_today
from app.core.config import get_settings
from app.core.current_user import get_current_user
from app.core.db import get_db
from app.models import ChatMessage, Conversation, Security, User, UserSettings
from app.repositories.assistant import (
    DEFAULT_TITLE, claude_history, conversation_messages, conversation_out, message_out, owned_conversation,
    resolve_api_key,
)
from app.repositories.user_settings import get_user_settings
from app.schemas.assistant import (
    AssistantSettingsOut, AssistantSettingsUpdate, ConversationDetail, ConversationIn, ConversationOut, MessageIn, ModelOut,
)
from app.services.assistant.catalog import MODELS, get_model
from app.services.assistant.chat import ChatRun
from app.services.assistant.prompt import system_prompt
from app.services.assistant.streaming import SessionMaker, sse_events, start_chat
from app.services.secrets import MissingSecretError, encrypt_secret

router = APIRouter(tags=["assistant"])
logger = logging.getLogger(__name__)


def _settings_out(row: UserSettings) -> AssistantSettingsOut:
    _, source = resolve_api_key(row)
    return AssistantSettingsOut(configured=source is not None, source=source, model=get_model(row.ai_model).id,
                                models=[ModelOut(id=m.id, label=m.label) for m in MODELS])


@router.get("/assistant/settings", response_model=AssistantSettingsOut)
def read_assistant_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AssistantSettingsOut:
    return _settings_out(get_user_settings(db, user.id))


@router.put("/assistant/settings", response_model=AssistantSettingsOut)
def update_assistant_settings(
    payload: AssistantSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> AssistantSettingsOut:
    row = get_user_settings(db, user.id)
    row.ai_model = payload.model
    if payload.remove_key:
        row.anthropic_key_enc = None
    elif payload.api_key:
        try:
            row.anthropic_key_enc = encrypt_secret(payload.api_key, get_settings().app_secret)
        except MissingSecretError:
            db.rollback()
            raise HTTPException(status_code=503, detail="Ajoutez APP_SECRET dans le fichier .env pour enregistrer une clé.")
    db.commit()
    return _settings_out(row)


@router.get("/assistant/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ConversationOut]:
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.updated_at.desc(), Conversation.id.desc()))
    return [conversation_out(db, c) for c in rows]


@router.post("/assistant/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ConversationOut:
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
def get_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ConversationDetail:
    conv = owned_conversation(db, user.id, conversation_id)
    return ConversationDetail(**conversation_out(db, conv).model_dump(),
                              messages=[message_out(m) for m in conversation_messages(db, conv.id)])


@router.delete("/assistant/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.delete(owned_conversation(db, user.id, conversation_id))
    db.commit()

@router.post("/assistant/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int, payload: MessageIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
    llm_factory: Callable = Depends(get_llm_factory), session_maker: SessionMaker = Depends(get_session_maker),
) -> StreamingResponse:
    conv = owned_conversation(db, user.id, conversation_id)
    row = get_user_settings(db, user.id)
    api_key, _ = resolve_api_key(row)
    if not api_key:
        raise HTTPException(status_code=409, detail="Aucune clé API Claude n'est configurée. Ajoutez-la dans les Réglages.")
    config = get_settings()
    model = get_model(row.ai_model)
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
                  system=system_prompt(paris_today(), row.min_orders_per_year, security),
                  history=history, execute_tool=None,
                  max_tokens=config.assistant_max_tokens, max_rounds=config.assistant_max_rounds)
    chat = start_chat(run, session_maker, conv.id, user.id, model)
    return StreamingResponse(sse_events(start, chat), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
