import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.intervention import Evidence
from app.services.exceptions import not_found, bad_request
from app.services.intervention_service import get_intervention_or_404


# ── Allowed MIME types ─────────────────────────────────────────────────────────

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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _intervention_upload_dir(intervention_id: int) -> Path:
    """Returns (and creates) the upload directory for a given intervention."""
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


# ── Service functions ──────────────────────────────────────────────────────────

async def upload_evidence(
    db: Session,
    intervention_id: int,
    file: UploadFile,
) -> Evidence:
    """
    Validates, stores the uploaded image on disk, and registers it in the DB.
    Returns the created Evidence ORM object.
    """
    # 1. Intervention must exist
    get_intervention_or_404(db, intervention_id)

    # 2. Validate MIME type reported by client
    mime = _validate_mime(file.content_type)

    # 3. Validate extension from original filename
    original_name = file.filename or "upload"
    ext = _safe_extension(original_name)

    # 4. Read content & enforce size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise bad_request(
            f"El archivo supera el tamaño máximo permitido de {MAX_FILE_SIZE_MB} MB."
        )
    if len(content) == 0:
        raise bad_request("El archivo está vacío.")

    # 5. Generate a unique filename to avoid collisions
    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = _intervention_upload_dir(intervention_id)
    file_path = upload_dir / stored_name

    # 6. Write to disk
    file_path.write_bytes(content)

    # 7. Store relative path in DB  (relative to MEDIA_DIR for portability)
    relative_path = str(
        Path("interventions") / str(intervention_id) / stored_name
    )

    evidence = Evidence(
        intervention_id=intervention_id,
        file_path=relative_path,
        original_filename=original_name,
        mime_type=mime,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, intervention_id: int) -> list[Evidence]:
    """Returns all evidence records for an intervention (validates it exists)."""
    get_intervention_or_404(db, intervention_id)
    return (
        db.query(Evidence)
        .filter(Evidence.intervention_id == intervention_id)
        .order_by(Evidence.created_at)
        .all()
    )


def get_evidence_file_path(db: Session, evidence_id: int) -> Path:
    """Resolves the absolute path of an evidence file (used by PDF generator)."""
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise not_found("Evidence", evidence_id)
    return Path(settings.media_dir) / evidence.file_path
