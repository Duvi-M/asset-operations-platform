from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.asset import AssetStatus
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetRead, AssetUpdate, AssetList
from app.services import asset_service, qr_service, audit_service

router = APIRouter(prefix="/assets", tags=["Assets"], dependencies=[Depends(get_current_user)])

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTANT: fixed-path routes (/scan/..., /qr) MUST be registered before
# parameterised routes (/{asset_id}) so FastAPI doesn't try to coerce the
# literal string "scan" into an integer path parameter.
# ─────────────────────────────────────────────────────────────────────────────


# ── Scan lookup — fixed path, registered first ────────────────────────────────

@router.get(
    "/scan/{code}",
    response_model=AssetRead,
    summary="Buscar un Asset por código escaneado",
    description=(
        "Resuelve un código escaneado (QR, serial o código interno) al Asset correspondiente.\n\n"
        "**Estrategias de búsqueda (en orden):**\n"
        "1. Patrón QR propio: `AOP-ASSET-{id}`\n"
        "2. `serial_number` — coincidencia exacta, sin distinción de mayúsculas\n"
        "3. `internal_code` — coincidencia exacta, sin distinción de mayúsculas\n\n"
        "Devuelve **404** si el código no coincide con ningún Asset."
    ),
)
def scan_asset(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    asset = qr_service.resolve_scan_code(db, code)
    audit_service.log_action(
        user_id=current_user.id,
        action="scan_asset",
        entity_type="asset",
        entity_id=asset.id,
        metadata={
            "code": code,
            "serial_number": asset.serial_number,
            "internal_code": asset.internal_code,
        },
    )
    return asset


# ── Collection endpoints ──────────────────────────────────────────────────────

@router.post(
    "",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un Asset (equipo físico)",
)
def create_asset(
    data: AssetCreate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
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
    search: str | None = Query(
        None,
        description="Busca en item_name, serial_number, internal_code, location",
    ),
    db: Session = Depends(get_db),
):
    total, items = asset_service.list_assets(
        db, skip=skip, limit=limit,
        status=status.value if status else None,
        search=search, part_id=part_id,
    )
    return AssetList(total=total, items=items)


# ── Single-asset endpoints — parameterised routes last ────────────────────────

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
def update_asset(
    asset_id: int,
    data: AssetUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    return asset_service.update_asset(db, asset_id, data)


@router.get(
    "/{asset_id}/qr",
    summary="Generar imagen PNG del código QR de un Asset",
    description=(
        "Genera y descarga una imagen PNG con el código QR del Asset.\n\n"
        "El QR contiene el valor `AOP-ASSET-{id}`, estable e inequívoco.\n"
        "La imagen incluye una etiqueta de texto con el identificador "
        "y el serial / código interno para lectura humana."
    ),
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "Imagen PNG del código QR.",
        },
        404: {"description": "Asset no encontrado."},
    },
)
def get_asset_qr(asset_id: int, db: Session = Depends(get_db)):
    # Validate asset exists first — returns 404 if not
    asset = asset_service.get_asset_or_404(db, asset_id)

    # Human-readable label: prefer serial, fall back to internal_code
    label = asset.serial_number or asset.internal_code or asset.item_name

    png_bytes = qr_service.generate_qr_png(asset_id=asset_id, label=label)

    filename = f"qr_asset_{asset_id}.png"
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(png_bytes)),
            # Allow caching — QR content never changes for a given ID
            "Cache-Control": "public, max-age=86400",
        },
    )
