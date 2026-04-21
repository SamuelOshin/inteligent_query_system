from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlmodel import Session

from app.db.database import get_session
from app.services.seed_service import run_one_time_seed
from app.utils.responses import success_response


router = APIRouter(prefix="/internal", tags=["internal"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/seed")
def seed_once(
    session: SessionDep,
    x_seed_token: Annotated[str | None, Header()] = None,
):
    result = run_one_time_seed(session, x_seed_token)
    return success_response(data=result)
