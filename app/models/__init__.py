# Re-export all models so Alembic and the app can import from one place
from app.models.part import Part
from app.models.asset import Asset, AssetStatus
from app.models.intervention import Intervention, InterventionAsset, Evidence, InterventionType
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog
from app.models.docs import (
    DocsDocument,
    DocsDocumentStatus,
    DocsFile,
    DocsItemReference,
    DocsReferenceType,
    DocsRelatedDocument,
    DocsRelationType,
    TechnicalItem,
    TechnicalItemDocument,
    TechnicalItemDocumentRelationType,
)
from app.models.work_order import WorkOrder, WorkOrderPriority, WorkOrderStatus

__all__ = [
    "Part",
    "Asset",
    "AssetStatus",
    "Intervention",
    "InterventionAsset",
    "Evidence",
    "InterventionType",
    "User",
    "UserRole",
    "AuditLog",
    "DocsDocument",
    "DocsDocumentStatus",
    "DocsFile",
    "DocsItemReference",
    "DocsReferenceType",
    "DocsRelatedDocument",
    "DocsRelationType",
    "TechnicalItem",
    "TechnicalItemDocument",
    "TechnicalItemDocumentRelationType",
    "WorkOrder",
    "WorkOrderPriority",
    "WorkOrderStatus",
]
