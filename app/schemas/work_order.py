from datetime import datetime

from pydantic import Field

from app.models.intervention import InterventionType
from app.models.work_order import WorkOrderPriority, WorkOrderStatus
from app.schemas.asset import AssetReadSlim
from app.schemas.base import AppModel


class WorkOrderUserRead(AppModel):
    id: int
    email: str
    full_name: str


class WorkOrderInterventionRead(AppModel):
    id: int
    type: InterventionType
    technician: str
    created_at: datetime


class WorkOrderCreate(AppModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)
    priority: WorkOrderPriority = WorkOrderPriority.MEDIUM
    status: WorkOrderStatus = WorkOrderStatus.OPEN
    asset_id: int = Field(..., gt=0)
    assigned_user_id: int | None = Field(None, gt=0)
    due_date: datetime | None = None


class WorkOrderUpdate(AppModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)
    priority: WorkOrderPriority | None = None
    status: WorkOrderStatus | None = None
    asset_id: int | None = Field(None, gt=0)
    assigned_user_id: int | None = Field(None, gt=0)
    due_date: datetime | None = None


class WorkOrderReadSlim(AppModel):
    id: int
    code: str
    title: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    asset_id: int
    assigned_user_id: int | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    due_date: datetime | None


class WorkOrderRead(WorkOrderReadSlim):
    description: str | None
    asset: AssetReadSlim
    assigned_user: WorkOrderUserRead | None = None
    creator: WorkOrderUserRead | None = None
    interventions: list[WorkOrderInterventionRead] = Field(default_factory=list)


class WorkOrderList(AppModel):
    total: int
    items: list[WorkOrderReadSlim]
