from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.models.work_order import WorkOrderPriority, WorkOrderStatus
from app.schemas.work_order import WorkOrderCreate, WorkOrderList, WorkOrderRead, WorkOrderUpdate
from app.services import audit_service, work_order_service

router = APIRouter(prefix="/work-orders", tags=["Work Orders"], dependencies=[Depends(get_current_user)])


@router.post(
    "",
    response_model=WorkOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una orden de trabajo",
)
def create_work_order(
    data: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    work_order = work_order_service.create_work_order(db, data, created_by=current_user.id)
    audit_service.log_action(
        user_id=current_user.id,
        action="create_work_order",
        entity_type="work_order",
        entity_id=work_order.id,
        metadata={
            "code": work_order.code,
            "asset_id": work_order.asset_id,
            "assigned_user_id": work_order.assigned_user_id,
            "status": work_order.status.value,
        },
    )
    return work_order


@router.get(
    "",
    response_model=WorkOrderList,
    summary="Listar órdenes de trabajo con filtros y paginación",
)
def list_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: WorkOrderStatus | None = Query(None),
    priority: WorkOrderPriority | None = Query(None),
    asset_id: int | None = Query(None, gt=0),
    assigned_user_id: int | None = Query(None, gt=0),
    search: str | None = Query(None, description="Busca en code, title y description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = work_order_service.list_work_orders(
        db,
        skip=skip,
        limit=limit,
        status=status,
        priority=priority,
        asset_id=asset_id,
        assigned_user_id=assigned_user_id,
        search=search,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="search_work_orders",
        entity_type="work_order",
        metadata={
            "skip": skip,
            "limit": limit,
            "status": status.value if status else None,
            "priority": priority.value if priority else None,
            "asset_id": asset_id,
            "assigned_user_id": assigned_user_id,
            "search": search,
            "total": total,
        },
    )
    return WorkOrderList(total=total, items=items)


@router.get(
    "/{work_order_id}",
    response_model=WorkOrderRead,
    summary="Obtener una orden de trabajo",
)
def get_work_order(
    work_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work_order = work_order_service.get_work_order_or_404(db, work_order_id)
    audit_service.log_action(
        user_id=current_user.id,
        action="view_work_order",
        entity_type="work_order",
        entity_id=work_order.id,
        metadata={"code": work_order.code},
    )
    return work_order


@router.patch(
    "/{work_order_id}",
    response_model=WorkOrderRead,
    summary="Actualizar una orden de trabajo",
)
def update_work_order(
    work_order_id: int,
    data: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    work_order = work_order_service.update_work_order(db, work_order_id, data)
    audit_service.log_action(
        user_id=current_user.id,
        action="update_work_order",
        entity_type="work_order",
        entity_id=work_order.id,
        metadata={
            "code": work_order.code,
            "updated_fields": sorted(data.model_dump(exclude_unset=True).keys()),
            "status": work_order.status.value,
        },
    )
    return work_order
