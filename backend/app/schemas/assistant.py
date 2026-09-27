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
