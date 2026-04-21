import hmac
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models.seed_execution import SeedExecution
from app.utils.exceptions import ConflictError, ForbiddenError, InternalError
from scripts.seed import seed


SEED_ACTION = "profiles_seed"


def _resolve_seed_file_path(configured_path: str) -> str:
    candidate = Path(configured_path)
    if candidate.is_absolute():
        return str(candidate)

    project_root = Path(__file__).resolve().parents[2]
    return str((project_root / candidate).resolve())


def run_one_time_seed(session: Session, provided_token: str | None):
    if not settings.INTERNAL_SEED_ENABLED:
        raise ForbiddenError("Seed endpoint is disabled")

    if not settings.INTERNAL_SEED_TOKEN:
        raise ForbiddenError("Seed token is not configured")

    if not provided_token or not hmac.compare_digest(provided_token, settings.INTERNAL_SEED_TOKEN):
        raise ForbiddenError("Invalid seed token")

    already_ran = session.exec(
        select(SeedExecution).where(SeedExecution.action == SEED_ACTION)
    ).first()
    if already_ran:
        raise ConflictError("Seed has already been executed")

    seed_file = _resolve_seed_file_path(settings.INTERNAL_SEED_FILE)

    try:
        inserted, skipped = seed(seed_file)
    except SystemExit as exc:
        raise InternalError("Seeding failed: invalid seed input") from exc
    except Exception as exc:
        raise InternalError("Seeding failed") from exc

    marker = SeedExecution(
        action=SEED_ACTION,
        seed_file=seed_file,
        inserted=inserted,
        skipped=skipped,
    )

    try:
        session.add(marker)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Seed has already been executed") from exc

    return {
        "message": "Seed executed successfully",
        "inserted": inserted,
        "skipped": skipped,
        "seed_file": seed_file,
    }
