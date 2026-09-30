import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.services.assistant.catalog import MODELS

SortKey = Literal["email", "first_name", "last_name", "role", "is_premium", "verified", "created_at", "last_login_at"]


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_premium: bool
    verified: bool
    has_password: bool
    has_google: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    role: Literal["user", "admin"] | None = None
    is_premium: bool | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value


class DeleteUserIn(BaseModel):
    confirm_email: str = Field(max_length=254)


class ModelChoice(BaseModel):
    id: str
    label: str


class AdminSettingsOut(BaseModel):
    ai_model: str
    ai_monthly_cost_limit_usd: float
    models: list[ModelChoice]


class AdminSettingsIn(BaseModel):
    ai_model: str
    ai_monthly_cost_limit_usd: float = Field(ge=0, le=1000)

    @field_validator("ai_model")
    @classmethod
    def known_model(cls, value: str) -> str:
        if value not in {m.id for m in MODELS}:
            raise ValueError("Modèle inconnu.")
        return value


class ConfigStatusOut(BaseModel):
    """Ce qui est renseigné dans .env : oui ou non, jamais la valeur."""

    claude: bool
    smtp: bool
    google: bool
    turnstile: bool
    app_secret: bool
    admin_email: bool
