import enum
from datetime import datetime, date
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class InterventionType(str, enum.Enum):
    """Type of field intervention."""
    INSTALLATION = "installation"
    SUPPORT = "support"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    REMOVAL = "removal"
    OTHER = "other"


class Intervention(Base):
    """
    Field intervention report.
    Created by technicians in the field before upload to RESCO.
    """
    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    type: Mapped[InterventionType] = mapped_column(
        Enum(
            InterventionType,
            name="intervention_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )

    rig: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    pozo: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    technician: Mapped[str] = mapped_column(String(200), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    intervention_assets: Mapped[list["InterventionAsset"]] = relationship(
        "InterventionAsset", back_populates="intervention", cascade="all, delete-orphan"
    )
    evidences: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="intervention", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Intervention id={self.id} type={self.type} rig={self.rig!r} date={self.date}>"


class InterventionAsset(Base):
    """
    Association between an Intervention and an Asset.
    Allows adding notes per asset within an intervention.
    """
    __tablename__ = "intervention_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    intervention_id: Mapped[int] = mapped_column(
        ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    location_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    intervention: Mapped["Intervention"] = relationship(
        "Intervention", back_populates="intervention_assets"
    )
    asset: Mapped["Asset"] = relationship("Asset", back_populates="intervention_assets")

    def __repr__(self) -> str:
        return f"<InterventionAsset intervention={self.intervention_id} asset={self.asset_id}>"


class Evidence(Base):
    """
    Photo or file evidence attached to an intervention.
    file_path stores the relative path under MEDIA_DIR.
    """
    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    intervention_id: Mapped[int] = mapped_column(
        ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    intervention: Mapped["Intervention"] = relationship(
        "Intervention", back_populates="evidences"
    )

    def __repr__(self) -> str:
        return f"<Evidence id={self.id} intervention={self.intervention_id} file={self.original_filename!r}>"