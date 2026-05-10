from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.intervention import InterventionType
from app.models.user import User
from app.schemas.intervention import (
    InterventionCreate, InterventionRead, InterventionUpdate, InterventionList,
    InterventionAssetCreate, InterventionAssetRead, InterventionReadSlim,
    EvidenceRead, EvidenceList,
)
from app.services import intervention_service, evidence_service, pdf_service, audit_service

router = APIRouter(prefix="/interventions", tags=["Interventions"], dependencies=[Depends(get_current_user)])


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=InterventionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un reporte de intervención",
)
def create_intervention(
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intervention = intervention_service.create_intervention(db, data)
    audit_service.log_action(
        user_id=current_user.id,
        action="create_intervention",
        entity_type="intervention",
        entity_id=intervention.id,
        metadata={"type": intervention.type.value, "rig": intervention.rig, "pozo": intervention.pozo},
    )
    return intervention


@router.get(
    "",
    response_model=InterventionList,
    summary="Listar intervenciones con filtros y paginación",
)
def list_interventions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    rig: str | None = Query(None),
    pozo: str | None = Query(None),
    technician: str | None = Query(None),
    type: InterventionType | None = Query(None),
    db: Session = Depends(get_db),
):
    total, items = intervention_service.list_interventions(
        db, skip=skip, limit=limit,
        rig=rig, pozo=pozo, technician=technician,
        type=type.value if type else None,
    )
    slim_items = [
        InterventionReadSlim(
            id=i.id,
            type=i.type,
            rig=i.rig,
            pozo=i.pozo,
            technician=i.technician,
            date=i.date,
            end_date=i.end_date,
            asset_count=len(i.intervention_assets),
            evidence_count=len(i.evidences),
        )
        for i in items
    ]
    return InterventionList(total=total, items=slim_items)


@router.get(
    "/{intervention_id}",
    response_model=InterventionRead,
    summary="Obtener una intervención completa (con assets y evidencias)",
)
def get_intervention(intervention_id: int, db: Session = Depends(get_db)):
    return intervention_service.get_intervention_or_404(db, intervention_id)


@router.patch(
    "/{intervention_id}",
    response_model=InterventionRead,
    summary="Actualizar campos de una intervención (PATCH)",
)
def update_intervention(
    intervention_id: int, data: InterventionUpdate, db: Session = Depends(get_db)
):
    return intervention_service.update_intervention(db, intervention_id, data)


# ── Assets ─────────────────────────────────────────────────────────────────────

@router.post(
    "/{intervention_id}/assets",
    response_model=InterventionAssetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Asociar un Asset a una intervención",
)
def add_asset(
    intervention_id: int,
    data: InterventionAssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    intervention_asset = intervention_service.add_asset_to_intervention(db, intervention_id, data)
    audit_service.log_action(
        user_id=current_user.id,
        action="associate_asset",
        entity_type="intervention",
        entity_id=intervention_id,
        metadata={
            "asset_id": data.asset_id,
            "location_note": data.location_note,
        },
    )
    return intervention_asset


# ── Evidence ───────────────────────────────────────────────────────────────────

@router.post(
    "/{intervention_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una fotografía / evidencia a una intervención",
    description=(
        "Sube una imagen (JPEG, PNG, WEBP, GIF, BMP, TIFF) de hasta 10 MB. "
        "El archivo se guarda en disco y se registra en la base de datos."
    ),
)
async def upload_evidence(
    intervention_id: int,
    file: UploadFile = File(..., description="Imagen a subir (máx. 10 MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evidence = await evidence_service.upload_evidence(db, intervention_id, file)
    audit_service.log_action(
        user_id=current_user.id,
        action="upload_evidence",
        entity_type="evidence",
        entity_id=evidence.id,
        metadata={
            "intervention_id": intervention_id,
            "filename": evidence.original_filename,
            "mime_type": evidence.mime_type,
        },
    )
    return evidence


@router.get(
    "/{intervention_id}/evidence",
    response_model=EvidenceList,
    summary="Listar evidencias de una intervención",
)
def list_evidence(intervention_id: int, db: Session = Depends(get_db)):
    items = evidence_service.list_evidence(db, intervention_id)
    return EvidenceList(total=len(items), items=items)


# ── PDF ────────────────────────────────────────────────────────────────────────

@router.get(
    "/{intervention_id}/pdf",
    summary="Generar y descargar el reporte PDF de una intervención",
    response_description="Archivo PDF del reporte de intervención",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF generado exitosamente.",
        },
        404: {"description": "Intervención no encontrada."},
    },
)
def download_pdf(intervention_id: int, db: Session = Depends(get_db)):
    pdf_bytes = pdf_service.generate_intervention_pdf(db, intervention_id)
    filename = f"intervencion_{intervention_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
