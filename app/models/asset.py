import enum
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class AssetStatus(str, enum.Enum):
    """Lifecycle status of a physical asset."""
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
    UNKNOWN = "unknown"


class Asset(Base):
    """
    Physical equipment instance (serialized or non-serialized).

    - Serialized assets: identified by serial_number
    - Non-serialized assets: identified by internal_code
    At least one of serial_number or internal_code must be present.
    """
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Reference to part catalog
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Identification — one of the two must be present (enforced at app level)
    serial_number: Mapped[str | None] = mapped_column(
        String(150), unique=True, nullable=True, index=True
    )
    internal_code: Mapped[str | None] = mapped_column(
        String(150), unique=True, nullable=True, index=True
    )

    # Descriptive fields
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus, name="asset_status"), nullable=False, default=AssetStatus.UNKNOWN
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="assets")
    intervention_assets: Mapped[list["InterventionAsset"]] = relationship(
        "InterventionAsset", back_populates="asset"
    )

    def __repr__(self) -> str:
        identifier = self.serial_number or self.internal_code
        return f"<Asset id={self.id} identifier={identifier!r} status={self.status}>"
