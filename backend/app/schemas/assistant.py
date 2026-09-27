from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.assistant.catalog import MODELS


class ModelOut(BaseModel):
    id: str
    label: str


class AssistantSettingsOut(BaseModel):
    configured: bool
    source: Literal["settings", "env"] | None
    model: str
    models: list[ModelOut]


class AssistantSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=20, max_length=300, pattern=r"^\S+$")
    remove_key: bool = False
    model: str

    @field_validator("model")
    @classmethod
    def known_model(cls, value: str) -> str:
        if value not in {m.id for m in MODELS}:
            raise ValueError("Modèle inconnu.")
        return value


class ConversationIn(BaseModel):
    security_id: int | None = None


class ConversationOut(BaseModel):
    id: int
    title: str
    security_id: int | None
    security_name: str | None
    security_symbol: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    tools: list[str]
    interrupted: bool
    error: str | None
    cost_usd: float
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message vide.")
        return value.strip()
