from datetime import datetime

from app.models.asset import AssetStatus
from app.models.docs import DocsDocumentStatus
from app.models.work_order import WorkOrderPriority, WorkOrderStatus
from app.schemas.base import AppModel


class DashboardWorkOrderItem(AppModel):
    id: int
    code: str
    title: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    asset_id: int
    assigned_user_id: int | None
    due_date: datetime | None


class DashboardWorkOrdersSummary(AppModel):
    open: int
    assigned: int
    in_progress: int
    completed_today: int
    critical_high: int
    overdue: int
    active_items: list[DashboardWorkOrderItem]


class DashboardInterventionItem(AppModel):
    id: int
    type: str
    rig: str
    pozo: str
    technician: str
    created_at: datetime
    work_order_id: int | None
    evidence_count: int


class DashboardInterventionsSummary(AppModel):
    recent_count: int
    with_evidence: int
    without_evidence: int
    linked_to_work_orders: int
    recent_items: list[DashboardInterventionItem]


class DashboardAssetItem(AppModel):
    id: int
    item_name: str
    serial_number: str | None
    internal_code: str | None
    status: AssetStatus
    updated_at: datetime


class DashboardAssetsSummary(AppModel):
    recently_updated: int
    in_maintenance: int
    with_maintenance_history: int
    with_technical_packet: int
    recent_items: list[DashboardAssetItem]


class DashboardDocsIssueItem(AppModel):
    id: int
    document_code: str
    title: str
    status: DocsDocumentStatus
    document_type: str
    expires_at: datetime | None
    issue: str


class DashboardDocsSummary(AppModel):
    active: int
    obsolete: int
    expired_certificates: int
    expiring_soon_certificates: int
    without_file: int
    without_references: int
    issue_items: list[DashboardDocsIssueItem]


class OperationalSummaryResponse(AppModel):
    work_orders: DashboardWorkOrdersSummary
    interventions: DashboardInterventionsSummary
    assets: DashboardAssetsSummary
    docs: DashboardDocsSummary
