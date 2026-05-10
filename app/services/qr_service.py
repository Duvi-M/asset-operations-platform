"""
QR / barcode service for Assets.

QR code content format
----------------------
  AOP-ASSET-{id}

This value is:
  - Stable (ID never changes)
  - Unambiguous (prefix prevents collisions with serial/internal codes)
  - Short enough for high-density QR at small sizes

Scan resolution order (GET /assets/scan/{code})
------------------------------------------------
  1. QR prefix pattern  →  AOP-ASSET-{id}  →  lookup by numeric ID
  2. serial_number      →  case-insensitive exact match
  3. internal_code      →  case-insensitive exact match

Image generation
----------------
  - Library : qrcode[pil]  (pure-Python QR + Pillow rendering)
  - Format  : PNG, returned as raw bytes
  - The PNG embeds a small AssetOps label below the QR matrix using
    Pillow's ImageDraw so the printout is human-readable too.
"""

import io
import re
import logging

import qrcode
import qrcode.constants
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.services.exceptions import not_found, service_unavailable

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

QR_PREFIX         = "AOP-ASSET-"
QR_PREFIX_PATTERN = re.compile(r"^AOP-ASSET-(\d+)$", re.IGNORECASE)

# Visual config
QR_BOX_SIZE   = 10    # pixels per QR module
QR_BORDER     = 4     # quiet-zone modules (QR spec minimum is 4)
LABEL_HEIGHT  = 28    # px strip below the QR matrix for the text label
LABEL_FONT_SZ = 13    # approximate font size (PIL default font is bitmap)
BG_COLOR      = (255, 255, 255)
FG_COLOR      = (18, 42, 74)   # BRAND_DARK — matches PDF palette


# ── Public helpers ─────────────────────────────────────────────────────────────

def asset_qr_value(asset_id: int) -> str:
    """Canonical QR content for a given asset ID."""
    return f"{QR_PREFIX}{asset_id}"


# ── Image generation ───────────────────────────────────────────────────────────

def generate_qr_png(asset_id: int, label: str | None = None) -> bytes:
    """
    Generate a QR code PNG for the given asset_id.

    Args:
        asset_id : The asset's numeric ID.
        label    : Optional single-line text printed below the QR
                   (e.g. serial number or item name).  Truncated at 40 chars.

    Returns:
        Raw PNG bytes ready to stream as a response.
    """
    qr_value = asset_qr_value(asset_id)

    # ── Build QR matrix ────────────────────────────────────────────────────────
    qr = qrcode.QRCode(
        version=None,                           # auto-select smallest version
        error_correction=qrcode.constants.ERROR_CORRECT_M,   # ~15 % recovery
        box_size=QR_BOX_SIZE,
        border=QR_BORDER,
    )
    qr.add_data(qr_value)
    qr.make(fit=True)

    qr_img: Image.Image = qr.make_image(
        fill_color=FG_COLOR,
        back_color=BG_COLOR,
    ).convert("RGB")

    qr_w, qr_h = qr_img.size

    # ── Compose final image with label strip ───────────────────────────────────
    total_h = qr_h + LABEL_HEIGHT
    final = Image.new("RGB", (qr_w, total_h), BG_COLOR)
    final.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(final)

    # Line separator
    draw.line([(8, qr_h), (qr_w - 8, qr_h)], fill=(200, 200, 200), width=1)

    # QR value (always shown — stable identifier)
    draw.text(
        (qr_w // 2, qr_h + 6),
        qr_value,
        fill=FG_COLOR,
        anchor="mt",            # middle-top anchor
    )

    # Optional human-readable label on second sub-line
    if label:
        short = label[:40]
        draw.text(
            (qr_w // 2, qr_h + 17),
            short,
            fill=(90, 90, 90),
            anchor="mt",
        )

    # ── Encode to PNG bytes ────────────────────────────────────────────────────
    buf = io.BytesIO()
    final.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ── Scan lookup ────────────────────────────────────────────────────────────────

def resolve_scan_code(db: Session, code: str) -> Asset:
    """
    Resolve a scanned code to an Asset using three strategies in order:

    1. QR prefix pattern  →  AOP-ASSET-{id}
    2. serial_number      →  case-insensitive exact match
    3. internal_code      →  case-insensitive exact match

    Raises HTTP 404 if no asset is found by any strategy.
    """
    code = code.strip()

    # ── Strategy 1: AOP-ASSET-{id} ───────────────────────────────────────────
    match = QR_PREFIX_PATTERN.match(code)
    if match:
        asset_id = int(match.group(1))
        try:
            asset = (
                db.query(Asset)
                .options(joinedload(Asset.part))
                .filter(Asset.id == asset_id)
                .first()
            )
        except Exception:
            logger.exception("Database error resolving QR asset id", extra={"asset_id": asset_id})
            raise service_unavailable("No fue posible resolver el código escaneado en este momento.")
        if asset:
            logger.info("Asset scan resolved by QR id", extra={"asset_id": asset_id})
            return asset
        # The QR code was well-formed but the ID doesn't exist
        raise not_found("Asset", asset_id)

    # ── Strategy 2: serial_number (case-insensitive) ───────────────────────────
    try:
        asset = (
            db.query(Asset)
            .options(joinedload(Asset.part))
            .filter(Asset.serial_number.ilike(code))
            .first()
        )
    except Exception:
        logger.exception("Database error resolving scan by serial", extra={"code": code})
        raise service_unavailable("No fue posible resolver el código escaneado en este momento.")
    if asset:
        logger.info("Asset scan resolved by serial", extra={"asset_id": asset.id})
        return asset

    # ── Strategy 3: internal_code (case-insensitive) ───────────────────────────
    try:
        asset = (
            db.query(Asset)
            .options(joinedload(Asset.part))
            .filter(Asset.internal_code.ilike(code))
            .first()
        )
    except Exception:
        logger.exception("Database error resolving scan by internal code", extra={"code": code})
        raise service_unavailable("No fue posible resolver el código escaneado en este momento.")
    if asset:
        logger.info("Asset scan resolved by internal code", extra={"asset_id": asset.id})
        return asset

    # Nothing found by any strategy
    logger.warning("Asset scan not found", extra={"code": code})
    raise not_found("Asset", code)
