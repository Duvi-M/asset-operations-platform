import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WorkOrderPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkOrderStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkOrder(Base):
    """Maintenance planning record between an Asset and field Interventions."""

    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[WorkOrderPriority] = mapped_column(
        Enum(
            WorkOrderPriority,
            name="work_order_priority",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=WorkOrderPriority.MEDIUM,
        index=True,
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        Enum(
            WorkOrderStatus,
            name="work_order_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=WorkOrderStatus.OPEN,
        index=True,
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    asset = relationship("Asset", back_populates="work_orders")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id], back_populates="assigned_work_orders")
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_work_orders")
    interventions = relationship("Intervention", back_populates="work_order")

    def __repr__(self) -> str:
        return f"<WorkOrder id={self.id} code={self.code!r} status={self.status}>"
