from pydantic import BaseModel, EmailStr, Field, field_validator


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
