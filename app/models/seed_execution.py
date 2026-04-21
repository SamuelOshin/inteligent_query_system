from datetime import datetime, timezone
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import DateTime


class SeedExecution(SQLModel, table=True):
    __tablename__ = "seed_executions"

    id: int | None = Field(default=None, primary_key=True)
    action: str = Field(index=True, unique=True, nullable=False)
    seed_file: str = Field(nullable=False)
    inserted: int = Field(default=0, nullable=False)
    skipped: int = Field(default=0, nullable=False)
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
