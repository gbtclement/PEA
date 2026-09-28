import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_premium: bool


class NoticeOut(BaseModel):
    message: str


class RegisterIn(BaseModel):
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    email: EmailStr
    password: str = Field(max_length=200)  # la règle 12–128 est vérifiée ensuite, avec un message clair
    accept_terms: bool

    @field_validator("first_name", "last_name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Champ obligatoire.")
        return value

    @field_validator("accept_terms")
    @classmethod
    def terms_accepted(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Les CGU et la politique de confidentialité doivent être acceptées.")
        return value


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\s*\d{6}\s*$")


class EmailIn(BaseModel):
    email: EmailStr


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)
    remember: bool = False


class ResetPasswordIn(BaseModel):
    token: str = Field(max_length=100)
    password: str = Field(max_length=200)


class TokenIn(BaseModel):
    token: str = Field(max_length=100)
