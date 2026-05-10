from datetime import datetime, date as Date
from pydantic import Field
from app.schemas.base import AppModel
from app.schemas.asset import AssetReadSlim
from app.models.intervention import InterventionType


# ── Evidence ───────────────────────────────────────────────────────────────────

class EvidenceRead(AppModel):
    id: int
    intervention_id: int
    file_path: str
    original_filename: str | None
    mime_type: str | None
    created_at: datetime


# ── InterventionAsset ──────────────────────────────────────────────────────────

class InterventionAssetCreate(AppModel):
    asset_id: int = Field(..., gt=0, examples=[1])
    location_note: str | None = Field(None, max_length=255, examples=["Cabina del operador"])
    notes: str | None = Field(None, max_length=2000, examples=["Cable dañado, pendiente revisión"])


class InterventionAssetRead(AppModel):
    id: int
    intervention_id: int
    asset_id: int
    asset: AssetReadSlim
    location_note: str | None
    notes: str | None
    created_at: datetime


# ── Intervention ───────────────────────────────────────────────────────────────

class InterventionCreate(AppModel):
    type: InterventionType = Field(..., examples=[InterventionType.INSTALLATION])
    rig: str = Field(..., min_length=1, max_length=150, examples=["RIG-07"])
    pozo: str = Field(..., min_length=1, max_length=150, examples=["POZO-A-14"])
    description: str | None = Field(None, max_length=5000)
    technician: str = Field(..., min_length=1, max_length=200, examples=["Juan Pérez"])
    date: Date = Field(..., examples=["2025-06-01"])
    end_date: Date | None = Field(None, examples=["2025-06-02"])


class InterventionUpdate(AppModel):
    """All fields optional — PATCH semantics."""
    type: InterventionType | None = None
    rig: str | None = Field(None, min_length=1, max_length=150)
    pozo: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = Field(None, max_length=5000)
    technician: str | None = Field(None, min_length=1, max_length=200)
    date: Date | None = None
    end_date: Date | None = None


class InterventionRead(AppModel):
    id: int
    type: InterventionType
    rig: str
    pozo: str
    description: str | None
    technician: str
    date: Date
    end_date: Date | None = None
    created_at: datetime
    updated_at: datetime
    intervention_assets: list[InterventionAssetRead] = []
    evidences: list[EvidenceRead] = []


class InterventionReadSlim(AppModel):
    """Lightweight list view without nested relations."""
    id: int
    type: InterventionType
    rig: str
    pozo: str
    technician: str
    date: Date
    end_date: Date | None = None
    asset_count: int = 0
    evidence_count: int = 0


class InterventionList(AppModel):
    total: int
    items: list[InterventionReadSlim]


class EvidenceList(AppModel):
    total: int
    items: list[EvidenceRead]
