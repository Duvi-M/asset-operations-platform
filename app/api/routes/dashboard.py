from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dashboard import OperationalSummaryResponse
from app.services import audit_service, dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)])


@router.get(
    "/operational-summary",
    response_model=OperationalSummaryResponse,
    summary="Obtener resumen operacional compacto",
)
def get_operational_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = dashboard_service.get_operational_summary(db, current_user)
    audit_service.log_action(
        user_id=current_user.id,
        action="view_operational_dashboard",
        entity_type="dashboard",
        metadata={"role": current_user.role.value},
    )
    return summary
