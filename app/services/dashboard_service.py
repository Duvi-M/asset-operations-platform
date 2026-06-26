from datetime import datetime, timedelta, timezone

from sqlalchemy import String, case, exists, func, or_
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetStatus
from app.models.docs import DocsDocument, DocsDocumentStatus, DocsFile, DocsItemReference, DocsReferenceType
from app.models.intervention import Evidence, Intervention, InterventionAsset
from app.models.user import User, UserRole
from app.models.work_order import WorkOrder, WorkOrderPriority, WorkOrderStatus
from app.schemas.dashboard import (
    DashboardAssetItem,
    DashboardAssetsSummary,
    DashboardDocsIssueItem,
    DashboardDocsSummary,
    DashboardInterventionItem,
    DashboardInterventionsSummary,
    DashboardWorkOrderItem,
    DashboardWorkOrdersSummary,
    OperationalSummaryResponse,
)

RECENT_DAYS = 30
ACTIVE_WORK_ORDER_STATUSES = (
    WorkOrderStatus.OPEN,
    WorkOrderStatus.ASSIGNED,
    WorkOrderStatus.IN_PROGRESS,
)


def get_operational_summary(db: Session, current_user: User) -> OperationalSummaryResponse:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    recent_start = now - timedelta(days=RECENT_DAYS)
    expiring_until = now + timedelta(days=30)

    is_admin = current_user.role == UserRole.ADMIN

    return OperationalSummaryResponse(
        work_orders=_build_work_orders_summary(
            db,
            user_id=None if is_admin else current_user.id,
            now=now,
            today_start=today_start,
            tomorrow_start=tomorrow_start,
        ),
        interventions=_build_interventions_summary(
            db,
            technician_name=None if is_admin else current_user.full_name,
            recent_start=recent_start,
        ),
        assets=_build_assets_summary(db, recent_start=recent_start),
        docs=_build_docs_summary(db, now=now, expiring_until=expiring_until),
    )


def _work_order_base_query(db: Session, user_id: int | None):
    q = db.query(WorkOrder)
    if user_id is not None:
        q = q.filter(WorkOrder.assigned_user_id == user_id)
    return q


def _build_work_orders_summary(
    db: Session,
    *,
    user_id: int | None,
    now: datetime,
    today_start: datetime,
    tomorrow_start: datetime,
) -> DashboardWorkOrdersSummary:
    base = _work_order_base_query(db, user_id)
    active = ACTIVE_WORK_ORDER_STATUSES

    priority_rank = case(
        (WorkOrder.priority == WorkOrderPriority.CRITICAL, 0),
        (WorkOrder.priority == WorkOrderPriority.HIGH, 1),
        (WorkOrder.priority == WorkOrderPriority.MEDIUM, 2),
        else_=3,
    )
    overdue_rank = case((WorkOrder.due_date < now, 0), else_=1)

    active_items = (
        base.filter(WorkOrder.status.in_(active))
        .order_by(overdue_rank.asc(), priority_rank.asc(), WorkOrder.due_date.asc().nullslast(), WorkOrder.id.desc())
        .limit(8)
        .all()
    )

    return DashboardWorkOrdersSummary(
        open=base.filter(WorkOrder.status == WorkOrderStatus.OPEN).count(),
        assigned=base.filter(WorkOrder.status == WorkOrderStatus.ASSIGNED).count(),
        in_progress=base.filter(WorkOrder.status == WorkOrderStatus.IN_PROGRESS).count(),
        completed_today=base.filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.updated_at >= today_start,
            WorkOrder.updated_at < tomorrow_start,
        ).count(),
        critical_high=base.filter(
            WorkOrder.status.in_(active),
            WorkOrder.priority.in_((WorkOrderPriority.HIGH, WorkOrderPriority.CRITICAL)),
        ).count(),
        overdue=base.filter(
            WorkOrder.status.in_(active),
            WorkOrder.due_date.isnot(None),
            WorkOrder.due_date < now,
        ).count(),
        active_items=[DashboardWorkOrderItem.model_validate(item) for item in active_items],
    )


def _intervention_base_query(db: Session, technician_name: str | None):
    q = db.query(Intervention)
    if technician_name is not None:
        q = q.filter(Intervention.technician == technician_name)
    return q


def _build_interventions_summary(
    db: Session,
    *,
    technician_name: str | None,
    recent_start: datetime,
) -> DashboardInterventionsSummary:
    base = _intervention_base_query(db, technician_name).filter(Intervention.created_at >= recent_start)
    evidence_exists = exists().where(Evidence.intervention_id == Intervention.id)

    evidence_counts = (
        db.query(
            Evidence.intervention_id.label("intervention_id"),
            func.count(Evidence.id).label("evidence_count"),
        )
        .group_by(Evidence.intervention_id)
        .subquery()
    )

    recent_rows = (
        base.outerjoin(evidence_counts, evidence_counts.c.intervention_id == Intervention.id)
        .with_entities(Intervention, func.coalesce(evidence_counts.c.evidence_count, 0).label("evidence_count"))
        .order_by(Intervention.created_at.desc(), Intervention.id.desc())
        .limit(5)
        .all()
    )

    return DashboardInterventionsSummary(
        recent_count=base.count(),
        with_evidence=base.filter(evidence_exists).count(),
        without_evidence=base.filter(~evidence_exists).count(),
        linked_to_work_orders=base.filter(Intervention.work_order_id.isnot(None)).count(),
        recent_items=[
            DashboardInterventionItem(
                id=intervention.id,
                type=intervention.type.value,
                rig=intervention.rig,
                pozo=intervention.pozo,
                technician=intervention.technician,
                created_at=intervention.created_at,
                work_order_id=intervention.work_order_id,
                evidence_count=int(evidence_count or 0),
            )
            for intervention, evidence_count in recent_rows
        ],
    )


def _build_assets_summary(db: Session, *, recent_start: datetime) -> DashboardAssetsSummary:
    history_exists = exists().where(InterventionAsset.asset_id == Asset.id)
    technical_packet_exists = exists().where(
        or_(
            (DocsItemReference.reference_type == DocsReferenceType.ASSET_ID)
            & (DocsItemReference.normalized_value == func.cast(Asset.id, String)),
            (Asset.serial_number.isnot(None))
            & (DocsItemReference.reference_type == DocsReferenceType.SERIAL_NUMBER)
            & (DocsItemReference.normalized_value == func.replace(func.upper(Asset.serial_number), "-", "")),
            (Asset.internal_code.isnot(None))
            & (DocsItemReference.reference_type == DocsReferenceType.INTERNAL_CODE)
            & (DocsItemReference.normalized_value == func.replace(func.upper(Asset.internal_code), "-", "")),
        )
    )
    recent_assets = (
        db.query(Asset)
        .filter(Asset.updated_at >= recent_start)
        .order_by(Asset.updated_at.desc(), Asset.id.desc())
        .limit(5)
        .all()
    )

    return DashboardAssetsSummary(
        recently_updated=db.query(Asset).filter(Asset.updated_at >= recent_start).count(),
        in_maintenance=db.query(Asset).filter(Asset.status == AssetStatus.MAINTENANCE).count(),
        with_maintenance_history=db.query(Asset).filter(history_exists).count(),
        with_technical_packet=db.query(Asset).filter(technical_packet_exists).count(),
        recent_items=[DashboardAssetItem.model_validate(asset) for asset in recent_assets],
    )


def _is_certificate_filter():
    return DocsDocument.document_type.ilike("%certificate%")


def _build_docs_summary(db: Session, *, now: datetime, expiring_until: datetime) -> DashboardDocsSummary:
    active = DocsDocument.status == DocsDocumentStatus.ACTIVE
    file_exists = exists().where(DocsFile.document_id == DocsDocument.id)
    reference_exists = exists().where(DocsItemReference.document_id == DocsDocument.id)

    issue_documents = (
        db.query(DocsDocument)
        .filter(
            active,
            or_(
                ~file_exists,
                ~reference_exists,
                _is_certificate_filter() & DocsDocument.expires_at.isnot(None) & (DocsDocument.expires_at < expiring_until),
            ),
        )
        .order_by(DocsDocument.expires_at.asc().nullslast(), DocsDocument.updated_at.desc(), DocsDocument.id.desc())
        .limit(5)
        .all()
    )
    issue_document_ids = [document.id for document in issue_documents]
    file_document_ids = set()
    reference_document_ids = set()
    if issue_document_ids:
        file_document_ids = {
            row[0]
            for row in db.query(DocsFile.document_id)
            .filter(DocsFile.document_id.in_(issue_document_ids))
            .all()
        }
        reference_document_ids = {
            row[0]
            for row in db.query(DocsItemReference.document_id)
            .filter(DocsItemReference.document_id.in_(issue_document_ids))
            .all()
        }
    without_file_ids = set(issue_document_ids) - file_document_ids
    without_reference_ids = set(issue_document_ids) - reference_document_ids

    return DashboardDocsSummary(
        active=db.query(DocsDocument).filter(active).count(),
        obsolete=db.query(DocsDocument).filter(DocsDocument.status == DocsDocumentStatus.OBSOLETE).count(),
        expired_certificates=db.query(DocsDocument).filter(
            _is_certificate_filter(),
            DocsDocument.expires_at.isnot(None),
            DocsDocument.expires_at < now,
        ).count(),
        expiring_soon_certificates=db.query(DocsDocument).filter(
            _is_certificate_filter(),
            DocsDocument.expires_at >= now,
            DocsDocument.expires_at <= expiring_until,
        ).count(),
        without_file=db.query(DocsDocument).filter(active, ~file_exists).count(),
        without_references=db.query(DocsDocument).filter(active, ~reference_exists).count(),
        issue_items=[
            _build_doc_issue_item(
                document,
                now,
                expiring_until,
                without_file_ids=without_file_ids,
                without_reference_ids=without_reference_ids,
            )
            for document in issue_documents
        ],
    )


def _build_doc_issue_item(
    document: DocsDocument,
    now: datetime,
    expiring_until: datetime,
    *,
    without_file_ids: set[int],
    without_reference_ids: set[int],
) -> DashboardDocsIssueItem:
    expires_at = _as_utc_aware(document.expires_at)
    is_certificate = "certificate" in document.document_type.lower()
    if is_certificate and expires_at and expires_at < now:
        issue = "expired_certificate"
    elif is_certificate and expires_at and expires_at <= expiring_until:
        issue = "expiring_soon_certificate"
    elif document.id in without_file_ids:
        issue = "without_file"
    elif document.id in without_reference_ids:
        issue = "without_references"
    else:
        issue = "issue"

    return DashboardDocsIssueItem(
        id=document.id,
        document_code=document.document_code,
        title=document.title,
        status=document.status,
        document_type=document.document_type,
        expires_at=document.expires_at,
        issue=issue,
    )


def _as_utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
