"""
Cloudinary storage service.

Responsabilidades:
  - upload_to_cloudinary(): sube bytes a Cloudinary, devuelve la URL segura
  - resolve_image_for_pdf(): dado un file_path de Evidence, devuelve algo que
    ReportLab puede usar como fuente de Image() — ya sea un path local (str)
    o un BytesIO descargado desde la URL de Cloudinary

Compatibilidad con datos existentes:
  - file_path que empieza con "http" → es Cloudinary (o cualquier URL)
  - file_path que no empieza con "http" → es una ruta local relativa a media_dir
  Esto garantiza que las evidencias subidas antes de la migración sigan
  funcionando sin ningún cambio en la base de datos.
"""

import io
import urllib.request
import urllib.error
import logging
from pathlib import Path

import cloudinary
import cloudinary.uploader

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    """True si CLOUDINARY_URL está seteado en el entorno."""
    return bool(settings.cloudinary_url)


def _ensure_configured() -> None:
    """
    Inicializa el SDK de Cloudinary usando CLOUDINARY_URL.
    Cloudinary SDK parsea la URL automáticamente si se setea
    la variable de entorno CLOUDINARY_URL, pero lo hacemos
    explícito para evitar depender del entorno del proceso.
    """
    if settings.cloudinary_url:
        cloudinary.config(cloudinary_url=settings.cloudinary_url)


def is_url(file_path: str) -> bool:
    """Detecta si un file_path almacenado es una URL remota o una ruta local."""
    return file_path.startswith("http://") or file_path.startswith("https://")


def upload_to_cloudinary(
    content: bytes,
    original_filename: str,
    intervention_id: int,
) -> str:
    """
    Sube los bytes de una imagen a Cloudinary.

    Args:
        content:           Bytes del archivo.
        original_filename: Nombre original (para preservar extensión).
        intervention_id:   Se usa como carpeta en Cloudinary para organización.

    Returns:
        URL segura (https) de la imagen en Cloudinary.

    Raises:
        RuntimeError: si la subida falla.
    """
    _ensure_configured()

    folder = f"asset-operations-platform/interventions/{intervention_id}"

    try:
        result = cloudinary.uploader.upload(
            content,
            folder=folder,
            resource_type="image",
            # Preserva el nombre original como parte del public_id para trazabilidad
            use_filename=True,
            unique_filename=True,
            overwrite=False,
        )
        return result["secure_url"]
    except Exception as exc:
        logger.exception(
            "Cloudinary upload failed",
            extra={"intervention_id": intervention_id, "filename": original_filename},
        )
        raise RuntimeError("No fue posible almacenar la imagen en este momento.") from exc


def resolve_image_for_pdf(file_path: str) -> io.BytesIO | str | None:
    """
    Resuelve la fuente de imagen para el generador de PDF.

    Lógica:
      - Si file_path es URL (Cloudinary) → descarga los bytes con SSL y devuelve BytesIO
      - Si file_path es ruta local → devuelve el path absoluto como string
        (para compatibilidad con evidencias pre-migración)
      - Si no existe o falla → devuelve None (el PDF mostrará placeholder)

    ReportLab's Image() acepta tanto str (path) como file-like objects (BytesIO).
    """
    import ssl

    if is_url(file_path):
        # Evidencia en Cloudinary → descargar bytes con SSL verificado
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(file_path, context=ctx, timeout=10) as response:
                return io.BytesIO(response.read())
        except Exception as exc:
            logger.warning("Could not download remote evidence image for PDF", extra={"file_path": file_path, "error": str(exc)})
            return None
    else:
        # Evidencia local (pre-migración) → resolver path absoluto
        abs_path = Path(settings.media_dir) / file_path
        if abs_path.exists():
            return str(abs_path)
        return None
