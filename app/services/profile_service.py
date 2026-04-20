"""
services/profile_service.py

All business logic and all error decisions live here.
Routes call these functions and get back a result or an exception bubbles up.

Contract:
  - On success  → return the data
  - On failure  → raise the appropriate custom exception from utils.exceptions
  - Never return None for required resources — if missing, raise NotFoundError
  - Never swallow exceptions silently
"""

import uuid
from typing import Optional

from sqlmodel import Session, select, func
from sqlalchemy import asc, desc
from sqlalchemy.exc import IntegrityError

from app.models.profile import Profile
from app.schemas.profile import ProfileFilterParams
from app.utils.pagination import build_pagination
from app.utils.exceptions import NotFoundError, InternalError, BadRequestError
from app.utils.query_parser import parse_nl_query


# ─── Column Map for Sorting ───────────────────────────────────────────────────

SORTABLE_COLUMNS = {
    "age": Profile.age,
    "created_at": Profile.created_at,
    "gender_probability": Profile.gender_probability,
}


# ─── Name Normalization ───────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Single source of truth for name normalization."""
    return name.strip().lower()


# ─── Core Filter Builder ──────────────────────────────────────────────────────

def _apply_filters(statement, params: dict):
    """
    Chains .where() conditions onto a select() statement.
    Used by both the count query and the data query — guarantees
    total always reflects the exact same filter set as the returned rows.
    """
    if params.get("gender"):
        statement = statement.where(Profile.gender == params["gender"])

    if params.get("age_group"):
        statement = statement.where(Profile.age_group == params["age_group"])

    if params.get("country_id"):
        statement = statement.where(Profile.country_id == params["country_id"])

    if params.get("min_age") is not None:
        statement = statement.where(Profile.age >= params["min_age"])

    if params.get("max_age") is not None:
        statement = statement.where(Profile.age <= params["max_age"])

    if params.get("min_gender_probability") is not None:
        statement = statement.where(
            Profile.gender_probability >= params["min_gender_probability"]
        )

    if params.get("min_country_probability") is not None:
        statement = statement.where(
            Profile.country_probability >= params["min_country_probability"]
        )

    return statement


# ─── Service Functions ────────────────────────────────────────────────────────

def get_profiles(session: Session, filter_params: ProfileFilterParams):
    """
    Returns (profiles list, pagination meta) for the given filters.
    Never raises — an empty result is valid and returns ([], meta).
    """
    params = filter_params.model_dump(exclude={"sort_by", "order", "page", "limit"})
    pagination = build_pagination(filter_params.page, filter_params.limit)

    # Count query — identical filters, no offset/limit
    count_stmt = select(func.count()).select_from(Profile)
    count_stmt = _apply_filters(count_stmt, params)
    total = session.exec(count_stmt).one()

    # Data query
    data_stmt = select(Profile)
    data_stmt = _apply_filters(data_stmt, params)

    sort_col = SORTABLE_COLUMNS.get(
        filter_params.sort_by or "created_at", Profile.created_at
    )
    direction = asc if (filter_params.order or "desc") == "asc" else desc
    data_stmt = data_stmt.order_by(direction(sort_col))
    data_stmt = data_stmt.offset(pagination.offset).limit(pagination.limit)

    profiles = session.exec(data_stmt).all()
    pagination.total = total
    return profiles, pagination


def search_profiles(session: Session, q: str, page: int = 1, limit: int = 10):
    """
    NL search — parses query string then delegates to get_profiles.
    Raises BadRequestError if query is whitespace-only or cannot be interpreted.
    """
    if not q.strip():
        raise BadRequestError("Unable to interpret query")

    try:
        filter_dict = parse_nl_query(q)
    except ValueError as e:
        raise BadRequestError(str(e))

    filter_params = ProfileFilterParams(
        gender=filter_dict.get("gender"),
        age_group=filter_dict.get("age_group"),
        country_id=filter_dict.get("country_id"),
        min_age=filter_dict.get("min_age"),
        max_age=filter_dict.get("max_age"),
        page=page,
        limit=limit,
    )
    return get_profiles(session, filter_params)


def get_profile_by_id(session: Session, profile_id: uuid.UUID) -> Profile:
    """
    Returns the profile or raises NotFoundError.
    Never returns None — callers don't need to check.
    """
    profile = session.get(Profile, profile_id)
    if not profile:
        raise NotFoundError("Profile not found")
    return profile


def get_profile_by_name(session: Session, name: str) -> Optional[Profile]:
    """
    Returns profile or None — used intentionally for idempotency checks.
    None here means "does not exist yet", which is a valid state.
    """
    stmt = select(Profile).where(Profile.name == normalize_name(name))
    return session.exec(stmt).first()


def create_profile(session: Session, profile_data: Profile) -> Profile:
    """
    Persists a new profile.
    On IntegrityError (concurrent duplicate insert): rolls back and returns
    the existing record that caused the conflict.
    On any other DB failure: raises InternalError.
    """
    try:
        session.add(profile_data)
        session.commit()
        session.refresh(profile_data)
        return profile_data
    except IntegrityError:
        session.rollback()
        existing = get_profile_by_name(session, profile_data.name)
        if existing:
            return existing
        raise InternalError("Failed to create profile due to a database conflict")


def delete_profile_by_id(session: Session, profile_id: uuid.UUID) -> None:
    """
    Deletes a profile by ID.
    Raises NotFoundError if the profile does not exist.
    """
    profile = get_profile_by_id(session, profile_id)  # raises if missing
    session.delete(profile)
    session.commit()
