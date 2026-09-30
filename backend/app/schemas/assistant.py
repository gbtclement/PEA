from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ModelOut(BaseModel):
    id: str
    label: str


class AssistantStatusOut(BaseModel):
    available: bool
    reason: Literal["premium", "not_configured", "limit_reached"] | None
    spent_usd: float
    limit_usd: float
    model: str  # libellé du modèle par défaut


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
