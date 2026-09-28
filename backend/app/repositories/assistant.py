import uuid
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ChatMessage, Conversation, Security, UserSettings
from app.schemas.assistant import ConversationOut, MessageOut
from app.services.secrets import decrypt_secret

KeySource = Literal["settings", "env"]
DEFAULT_TITLE = "Nouvelle conversation"


def resolve_api_key(settings_row: UserSettings) -> tuple[str | None, KeySource | None]:
    """Clé saisie dans les Réglages en priorité, sinon ANTHROPIC_API_KEY."""
    config = get_settings()
    if settings_row.anthropic_key_enc:
        key = decrypt_secret(settings_row.anthropic_key_enc, config.app_secret)
        if key:
            return key, "settings"
    if config.anthropic_api_key:
        return config.anthropic_api_key, "env"
    return None, None


def owned_conversation(db: Session, user_id: uuid.UUID, conversation_id: int) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return conv


def conversation_messages(db: Session, conversation_id: int) -> list[ChatMessage]:
    return list(db.scalars(select(ChatMessage).where(ChatMessage.conversation_id == conversation_id)
                           .order_by(ChatMessage.created_at, ChatMessage.id)))


def conversation_out(db: Session, conv: Conversation) -> ConversationOut:
    security = db.get(Security, conv.security_id) if conv.security_id else None
    return ConversationOut(
        id=conv.id, title=conv.title, security_id=conv.security_id,
        security_name=security.name if security else None, security_symbol=security.symbol if security else None,
        input_tokens=conv.input_tokens, output_tokens=conv.output_tokens, cost_usd=round(conv.cost_usd, 4),
        created_at=conv.created_at, updated_at=conv.updated_at,
    )


def message_out(msg: ChatMessage) -> MessageOut:
    return MessageOut(id=msg.id, role=msg.role, content=msg.content, tools=list(msg.tools or []),
                      interrupted=msg.interrupted, error=msg.error, cost_usd=round(msg.cost_usd, 4),
                      created_at=msg.created_at)


def claude_history(messages: list[ChatMessage]) -> list[dict]:
    """Historique texte seul : les messages vides sont ignorés et deux messages du même rôle fusionnés."""
    history: list[dict] = []
    for msg in messages:
        if not msg.content.strip():
            continue
        if history and history[-1]["role"] == msg.role:
            history[-1]["content"] += "\n\n" + msg.content
        else:
            history.append({"role": msg.role, "content": msg.content})
    return history
