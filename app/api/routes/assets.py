from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import AssetStatus
from app.schemas.asset import AssetCreate, AssetRead, AssetUpdate, AssetList
from app.services import asset_service

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post(
    "",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un Asset (equipo físico)",
)
def create_asset(data: AssetCreate, db: Session = Depends(get_db)):
    return asset_service.create_asset(db, data)


@router.get(
    "",
    response_model=AssetList,
    summary="Listar Assets con filtros y paginación",
)
def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: AssetStatus | None = Query(None, description="Filtrar por estado"),
    part_id: int | None = Query(None, description="Filtrar por Part"),
    search: str | None = Query(None, description="Busca en item_name, serial, code, location"),
    db: Session = Depends(get_db),
):
    total, items = asset_service.list_assets(
        db, skip=skip, limit=limit,
        status=status.value if status else None,
        search=search, part_id=part_id,
    )
    return AssetList(total=total, items=items)


@router.get(
    "/{asset_id}",
    response_model=AssetRead,
    summary="Obtener un Asset por ID",
)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    return asset_service.get_asset_or_404(db, asset_id)


@router.patch(
    "/{asset_id}",
    response_model=AssetRead,
    summary="Actualizar campos de un Asset (PATCH)",
)
def update_asset(asset_id: int, data: AssetUpdate, db: Session = Depends(get_db)):
    return asset_service.update_asset(db, asset_id, data)
