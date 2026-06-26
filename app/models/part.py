from datetime import datetime
from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Part(Base):
    """
    Equipment catalog (part/model definition).
    Imported from TAT Excel exports.
    """
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    part_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="part")

    def __repr__(self) -> str:
        return f"<Part id={self.id} part_number={self.part_number!r}>"
