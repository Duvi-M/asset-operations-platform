import uuid
import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.intervention import Evidence
from app.services.exceptions import not_found, bad_request, service_unavailable
from app.services.intervention_service import get_intervention_or_404
from app.services import cloudinary_service

logger = logging.getLogger(__name__)

# ── Allowed types ──────────────────────────────────────────────────────────────

ALLOWED_MIME_TYPES: set[str] = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
}

ALLOWED_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"
}

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ── Validation helpers (unchanged) ────────────────────────────────────────────

def _intervention_upload_dir(intervention_id: int) -> Path:
    path = Path(settings.media_dir) / "interventions" / str(intervention_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise bad_request(
            f"Extensión '{ext}' no permitida. "
            f"Extensiones válidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    return ext


def _validate_mime(content_type: str | None) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_MIME_TYPES:
        raise bad_request(
            f"Tipo de archivo '{ct}' no permitido. "
            f"Solo se aceptan imágenes: {', '.join(sorted(ALLOWED_MIME_TYPES))}."
        )
    return ct


# ── Storage backend ───────────────────────────────────────────────────────────

def _store_file(content: bytes, original_name: str, intervention_id: int) -> str:
    """
    Guarda el archivo en el backend correcto y devuelve el valor
    a persistir en Evidence.file_path.

    - Si CLOUDINARY_URL está configurado → sube a Cloudinary → devuelve URL
    - Si no → guarda en disco local → devuelve ruta relativa
    """
    if cloudinary_service._is_configured():
        # ── Cloudinary (producción) ────────────────────────────────────────────
        url = cloudinary_service.upload_to_cloudinary(
            content=content,
            original_filename=original_name,
            intervention_id=intervention_id,
        )
        return url  # e.g. "https://res.cloudinary.com/mycloud/image/upload/..."
    else:
        # ── Local filesystem (desarrollo) ──────────────────────────────────────
        ext = _safe_extension(original_name)
        stored_name = f"{uuid.uuid4().hex}{ext}"
        upload_dir = _intervention_upload_dir(intervention_id)
        (upload_dir / stored_name).write_bytes(content)
        return str(Path("interventions") / str(intervention_id) / stored_name)


# ── Public service functions (signatures unchanged) ────────────────────────────

async def upload_evidence(
    db: Session,
    intervention_id: int,
    file: UploadFile,
) -> Evidence:
    """
    Valida la imagen, la almacena (Cloudinary o local según config),
    y registra el Evidence en la base de datos.
    """
    # 1. Intervention must exist
    get_intervention_or_404(db, intervention_id)

    # 2. Validate MIME
    mime = _validate_mime(file.content_type)

    # 3. Validate extension
    original_name = file.filename or "upload"
    _safe_extension(original_name)  # raises if invalid

    # 4. Read & validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise bad_request(
            f"El archivo supera el tamaño máximo permitido de {MAX_FILE_SIZE_MB} MB."
        )
    if len(content) == 0:
        raise bad_request("El archivo está vacío.")

    # 5. Store (Cloudinary or local) — returns the value for file_path
    try:
        stored_path = _store_file(content, original_name, intervention_id)
    except RuntimeError as exc:
        logger.warning(
            "Evidence storage rejected",
            extra={"intervention_id": intervention_id, "filename": original_name, "reason": str(exc)},
        )
        raise service_unavailable("No fue posible almacenar la evidencia en este momento.")

    # 6. Persist in DB
    evidence = Evidence(
        intervention_id=intervention_id,
        file_path=stored_path,      # URL ("https://...") or relative path
        original_filename=original_name,
        mime_type=mime,
    )
    db.add(evidence)
    try:
        db.commit()
        db.refresh(evidence)
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error uploading evidence",
            extra={"intervention_id": intervention_id, "filename": original_name},
        )
        raise service_unavailable("No fue posible registrar la evidencia en este momento.")
    logger.info(
        "Evidence uploaded",
        extra={"intervention_id": intervention_id, "evidence_id": evidence.id, "filename": original_name},
    )
    return evidence


def list_evidence(db: Session, intervention_id: int) -> list[Evidence]:
    get_intervention_or_404(db, intervention_id)
    try:
        return (
            db.query(Evidence)
            .filter(Evidence.intervention_id == intervention_id)
            .order_by(Evidence.created_at)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error listing evidence", extra={"intervention_id": intervention_id})
        raise service_unavailable("No fue posible listar las evidencias en este momento.")


def get_evidence_file_path(db: Session, evidence_id: int) -> Path:
    """Kept for backward compatibility. PDF service uses cloudinary_service directly."""
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise not_found("Evidence", evidence_id)
    return Path(settings.media_dir) / evidence.file_path
