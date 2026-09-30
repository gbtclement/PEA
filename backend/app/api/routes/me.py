from fastapi import APIRouter, Depends

from app.core.current_user import get_current_user
from app.models import User
from app.schemas.auth import MeOut

router = APIRouter(tags=["account"])


@router.get("/me", response_model=MeOut)
def read_me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut.model_validate(user)
