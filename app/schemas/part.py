from datetime import datetime
from pydantic import Field
from app.schemas.base import AppModel


# ── Write schemas ──────────────────────────────────────────────────────────────

class PartCreate(AppModel):
    part_number: str = Field(..., min_length=1, max_length=100, examples=["PN-001"])
    description: str | None = Field(None, max_length=2000, examples=["Sensor de presión"])


class PartUpdate(AppModel):
    """All fields optional — PATCH semantics."""
    part_number: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)


# ── Read schema ────────────────────────────────────────────────────────────────

class PartRead(AppModel):
    id: int
    part_number: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# ── List response ──────────────────────────────────────────────────────────────

class PartList(AppModel):
    total: int
    items: list[PartRead]
