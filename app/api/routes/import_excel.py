"""
Router: /api/v1/import
Handles Excel file imports for Parts and Assets.
"""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.excel_import import ImportResult
from app.services import excel_import_service

router = APIRouter(prefix="/import", tags=["Import"])

ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/octet-stream",   # Some browsers send this for .xlsx
    "application/zip",            # .xlsx is a ZIP — some clients report this
}
MAX_UPLOAD_MB  = 20
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@router.post(
    "/excel",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Importar inventario desde un archivo Excel (.xlsx)",
    description=(
        "Carga un archivo `.xlsx` exportado del sistema TAT y realiza un upsert "
        "de Parts y Assets en la base de datos.\n\n"
        "**Columnas reconocidas** (el nombre exacto no importa, se detecta por alias):\n"
        "- `Part Number` / `PN` / `Part#`\n"
        "- `Serial Number` / `SN` / `Serial No`\n"
        "- `Internal Code` / `Code` / `Asset Code`\n"
        "- `Item Name` / `Description`\n"
        "- `System Status` / `Status`\n"
        "- `Rig Location` / `Location`\n"
        "- `Size`\n\n"
        "**Reglas de upsert:**\n"
        "- `PartNumber` → crea o reutiliza el Part existente.\n"
        "- `Serial Number` identifica el Asset (si existe).\n"
        "- Si no hay Serial Number, se usa `Internal Code`.\n"
        "- Assets existentes se actualizan si hay cambios; filas sin cambios "
        "se reportan como `rows_skipped`.\n"
        "- Cada fila usa un savepoint individual — una fila errónea no cancela las demás.\n\n"
        f"**Límite:** {MAX_UPLOAD_MB} MB · 10 000 filas de datos."
    ),
)
async def import_excel(
    file: UploadFile = File(
        ...,
        description="Archivo .xlsx del TAT (máx. 20 MB)",
    ),
    sheet: str | None = Query(
        None,
        description=(
            "Nombre de la hoja a procesar. "
            "Si se omite, se usa la primera hoja activa."
        ),
    ),
    db: Session = Depends(get_db),
):
    # ── Filename extension check ───────────────────────────────────────────────
    filename = file.filename or "upload.xlsx"
    if not filename.lower().endswith(".xlsx"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": (
                    f"El archivo '{filename}' no tiene extensión .xlsx. "
                    "Solo se aceptan archivos Excel en formato .xlsx (Excel 2007+)."
                )
            },
        )

    # ── Read & size check ──────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "El archivo está vacío."},
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": (
                    f"El archivo supera el tamaño máximo permitido de {MAX_UPLOAD_MB} MB. "
                    f"Tamaño recibido: {len(file_bytes) / 1024 / 1024:.1f} MB."
                )
            },
        )

    # ── Run import ─────────────────────────────────────────────────────────────
    try:
        result = excel_import_service.import_excel(
            db=db,
            file_bytes=file_bytes,
            filename=filename,
            sheet_name=sheet,
        )
    except ValueError as exc:
        # Known errors: bad file format, sheet not found
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )
    except RuntimeError as exc:
        # DB commit failed
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    return result
