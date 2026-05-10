from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.schemas.part import PartCreate, PartRead, PartUpdate, PartList
from app.services import part_service

router = APIRouter(prefix="/parts", tags=["Parts"], dependencies=[Depends(get_current_user)])


@router.post(
    "",
    response_model=PartRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un Part (modelo de equipo)",
)
def create_part(
    data: PartCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return part_service.create_part(db, data)


@router.get(
    "",
    response_model=PartList,
    summary="Listar Parts con paginación y búsqueda",
)
def list_parts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: str | None = Query(None, description="Busca en part_number y description"),
    db: Session = Depends(get_db),
):
    total, items = part_service.list_parts(db, skip=skip, limit=limit, search=search)
    return PartList(total=total, items=items)


@router.get(
    "/{part_id}",
    response_model=PartRead,
    summary="Obtener un Part por ID",
)
def get_part(part_id: int, db: Session = Depends(get_db)):
    return part_service.get_part_or_404(db, part_id)


@router.patch(
    "/{part_id}",
    response_model=PartRead,
    summary="Actualizar campos de un Part (PATCH)",
)
def update_part(
    part_id: int,
    data: PartUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return part_service.update_part(db, part_id, data)
