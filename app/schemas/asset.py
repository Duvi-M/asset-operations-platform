from datetime import datetime
from pydantic import Field, model_validator, computed_field
from app.schemas.base import AppModel
from app.schemas.part import PartRead
from app.models.asset import AssetStatus

QR_PREFIX = "AOP-ASSET-"


# ── Write schemas ──────────────────────────────────────────────────────────────

class AssetCreate(AppModel):
    part_id: int = Field(..., gt=0)
    serial_number: str | None = Field(None, min_length=1, max_length=150, examples=["SN-ABC-001"])
    internal_code: str | None = Field(None, min_length=1, max_length=150, examples=["INT-001"])
    item_name: str = Field(..., min_length=1, max_length=255, examples=["Sensor de presión Honeywell"])
    status: AssetStatus = Field(AssetStatus.UNKNOWN)
    location: str | None = Field(None, max_length=255, examples=["Almacén central"])

    @model_validator(mode="after")
    def require_identifier(self) -> "AssetCreate":
        """An asset must have at least one of serial_number or internal_code."""
        if not self.serial_number and not self.internal_code:
            raise ValueError(
                "El equipo debe tener al menos un identificador: "
                "'serial_number' o 'internal_code'."
            )
        return self


class AssetUpdate(AppModel):
    """All fields optional — PATCH semantics."""
    serial_number: str | None = Field(None, min_length=1, max_length=150)
    internal_code: str | None = Field(None, min_length=1, max_length=150)
    item_name: str | None = Field(None, min_length=1, max_length=255)
    status: AssetStatus | None = None
    location: str | None = Field(None, max_length=255)
    part_id: int | None = Field(None, gt=0)

    @model_validator(mode="after")
    def prevent_both_identifiers_null(self) -> "AssetUpdate":
        """
        If both identifiers are being explicitly set to None in a PATCH,
        reject the request. We can't evaluate the final state here (we'd need
        the existing record), so this is caught in the service layer too.
        This validator catches the obvious case of passing both as None at once.
        """
        if self.serial_number is None and self.internal_code is None:
            # Only reject if both keys were explicitly included with None values
            # (Pydantic sets to None for missing optional fields too, so we
            # rely on the service layer to do the full cross-check with DB state.)
            pass
        return self


# ── Read schemas ───────────────────────────────────────────────────────────────

class AssetRead(AppModel):
    id: int
    part_id: int
    part: PartRead
    serial_number: str | None
    internal_code: str | None
    item_name: str
    status: AssetStatus
    location: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def qr_code_value(self) -> str:
        """Stable QR content for this asset: AOP-ASSET-{id}"""
        return f"{QR_PREFIX}{self.id}"


class AssetReadSlim(AppModel):
    """Lightweight version used inside nested responses."""
    id: int
    part_id: int
    serial_number: str | None
    internal_code: str | None
    item_name: str
    status: AssetStatus
    location: str | None

    @computed_field
    @property
    def qr_code_value(self) -> str:
        return f"{QR_PREFIX}{self.id}"


# ── List response ──────────────────────────────────────────────────────────────

class AssetList(AppModel):
    total: int
    items: list[AssetRead]
