"""
routes/profiles.py

Route layer only. No business logic. No try/except. No if/else on results.

Each route:
  1. Receives request params
  2. Calls the service
  3. Serializes the result through a response util
  4. Returns

All errors are raised as custom exceptions in the service layer.
main.py registers handlers that catch them and call error_response().
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlmodel import Session

from app.db.database import get_session
from app.schemas.profile import (
    ProfileFilterParams,
    ProfileListItemResponse,
    ProfileResponse,
)
from app.services import profile_service
from app.utils.responses import success_response, success_list_response

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

SessionDep = Annotated[Session, Depends(get_session)]


# ─── GET /api/profiles ────────────────────────────────────────────────────────

@router.get("/")
def list_profiles(
    session: SessionDep,
    gender: Annotated[str | None, Query()] = None,
    age_group: Annotated[str | None, Query()] = None,
    country_id: Annotated[str | None, Query()] = None,
    min_age: Annotated[int | None, Query(ge=0)] = None,
    max_age: Annotated[int | None, Query(ge=0)] = None,
    min_gender_probability: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    min_country_probability: Annotated[float | None, Query(ge=0.0, le=1.0)] = None,
    sort_by: Annotated[str | None, Query()] = None,
    order: Annotated[str | None, Query()] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    filter_params = ProfileFilterParams(
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
        sort_by=sort_by,
        order=order,
        page=page,
        limit=limit,
    )
    profiles, pagination = profile_service.get_profiles(session, filter_params)

    return success_list_response(
        data=[ProfileListItemResponse.model_validate(p).model_dump() for p in profiles],
        total=pagination.total,
        page=pagination.page,
        limit=pagination.limit,
    )


# ─── GET /api/profiles/search ─────────────────────────────────────────────────
# NOTE: declared before /{profile_id} — FastAPI matches routes top-down.
# "search" must not be parsed as a UUID.

@router.get("/search")
def search_profiles(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1)],
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    profiles, pagination = profile_service.search_profiles(
        session, q, page=page, limit=limit
    )

    return success_list_response(
        data=[ProfileListItemResponse.model_validate(p).model_dump() for p in profiles],
        total=pagination.total,
        page=pagination.page,
        limit=pagination.limit,
    )


# ─── GET /api/profiles/{id} ───────────────────────────────────────────────────

@router.get("/{profile_id}")
def get_profile(profile_id: uuid.UUID, session: SessionDep):
    profile = profile_service.get_profile_by_id(session, profile_id)

    return success_response(
        data=ProfileResponse.model_validate(profile).model_dump(mode="json"),
    )


# ─── DELETE /api/profiles/{id} ────────────────────────────────────────────────

@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: uuid.UUID, session: SessionDep):
    profile_service.delete_profile_by_id(session, profile_id)
    return Response(status_code=204)
