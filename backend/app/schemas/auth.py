import uuid

from pydantic import BaseModel, ConfigDict


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_premium: bool


class MessageOut(BaseModel):
    message: str
