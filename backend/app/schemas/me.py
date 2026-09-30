import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ProfileIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value


class PasswordChangeIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=200)
    new_password: str = Field(max_length=200)


class EmailChangeIn(BaseModel):
    new_email: EmailStr
    password: str | None = Field(default=None, max_length=200)


class CodeIn(BaseModel):
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class SessionOut(BaseModel):
    id: uuid.UUID
    device: str
    ip: str | None
    created_at: datetime
    last_seen_at: datetime
    current: bool


class DeleteAccountIn(BaseModel):
    confirm_email: str = Field(max_length=254)
    password: str | None = Field(default=None, max_length=200)


class AcceptTermsIn(BaseModel):
    accept_terms: bool

    @field_validator("accept_terms")
    @classmethod
    def must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Acceptez les CGU et la politique de confidentialité pour continuer.")
        return value


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str  # pending | ready
    created_at: datetime
    expires_at: datetime | None
