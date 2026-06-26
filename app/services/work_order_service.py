import logging
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderPriority, WorkOrderStatus
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate
from app.services.exceptions import bad_request, conflict, not_found, service_unavailable

logger = logging.getLogger(__name__)


def _format_work_order_code(work_order_id: int) -> str:
    return f"WO-{work_order_id:06d}"


def _work_order_query(db: Session):
    return db.query(WorkOrder).options(
        joinedload(WorkOrder.asset),
        joinedload(WorkOrder.assigned_user),
        joinedload(WorkOrder.creator),
        joinedload(WorkOrder.interventions),
    )


def _ensure_asset_exists(db: Session, asset_id: int) -> None:
    if not db.get(Asset, asset_id):
        raise not_found("Asset", asset_id)


def _ensure_user_exists(db: Session, user_id: int | None) -> None:
    if user_id is None:
        return
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise not_found("User", user_id)


def _validate_assignment(status: WorkOrderStatus | None, assigned_user_id: int | None) -> None:
    if status in {WorkOrderStatus.ASSIGNED, WorkOrderStatus.IN_PROGRESS} and assigned_user_id is None:
        raise bad_request("assigned_user_id es requerido para work orders assigned o in_progress.")


def get_work_order_or_404(db: Session, work_order_id: int) -> WorkOrder:
    try:
        work_order = _work_order_query(db).filter(WorkOrder.id == work_order_id).first()
    except SQLAlchemyError:
        logger.exception("Database error loading work order", extra={"work_order_id": work_order_id})
        raise service_unavailable("No fue posible consultar la orden de trabajo en este momento.")
    if not work_order:
        raise not_found("WorkOrder", work_order_id)
    return work_order


def create_work_order(db: Session, data: WorkOrderCreate, created_by: int | None) -> WorkOrder:
    _ensure_asset_exists(db, data.asset_id)
    _ensure_user_exists(db, data.assigned_user_id)
    _validate_assignment(data.status, data.assigned_user_id)

    payload = data.model_dump()
    work_order = WorkOrder(
        **payload,
        created_by=created_by,
        code=f"PENDING-{uuid4().hex[:8]}",
    )
    db.add(work_order)
    try:
        db.flush()
        work_order.code = _format_work_order_code(work_order.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Work order create conflict", extra={"asset_id": data.asset_id})
        raise conflict("No fue posible generar un código único para la orden de trabajo.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating work order")
        raise service_unavailable("No fue posible crear la orden de trabajo en este momento.")
    return get_work_order_or_404(db, work_order.id)


def list_work_orders(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    status: WorkOrderStatus | None = None,
    priority: WorkOrderPriority | None = None,
    asset_id: int | None = None,
    assigned_user_id: int | None = None,
    search: str | None = None,
) -> tuple[int, list[WorkOrder]]:
    q = db.query(WorkOrder)

    if status:
        q = q.filter(WorkOrder.status == status)
    if priority:
        q = q.filter(WorkOrder.priority == priority)
    if asset_id:
        q = q.filter(WorkOrder.asset_id == asset_id)
    if assigned_user_id:
        q = q.filter(WorkOrder.assigned_user_id == assigned_user_id)
    if search:
        like = f"%{search}%"
        q = q.filter(
            WorkOrder.code.ilike(like)
            | WorkOrder.title.ilike(like)
            | WorkOrder.description.ilike(like)
        )

    try:
        total = q.count()
        items = (
            q.order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error listing work orders", extra={"skip": skip, "limit": limit})
        raise service_unavailable("No fue posible listar las órdenes de trabajo en este momento.")
    return total, items


def update_work_order(db: Session, work_order_id: int, data: WorkOrderUpdate) -> WorkOrder:
    work_order = get_work_order_or_404(db, work_order_id)
    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return work_order

    if "asset_id" in patch:
        _ensure_asset_exists(db, patch["asset_id"])
    if "assigned_user_id" in patch:
        _ensure_user_exists(db, patch["assigned_user_id"])

    next_status = patch.get("status", work_order.status)
    next_assigned_user_id = patch.get("assigned_user_id", work_order.assigned_user_id)
    _validate_assignment(next_status, next_assigned_user_id)

    for field, value in patch.items():
        setattr(work_order, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Work order update conflict", extra={"work_order_id": work_order_id})
        raise conflict("No fue posible actualizar la orden de trabajo.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error updating work order", extra={"work_order_id": work_order_id})
        raise service_unavailable("No fue posible actualizar la orden de trabajo en este momento.")
    return get_work_order_or_404(db, work_order_id)
