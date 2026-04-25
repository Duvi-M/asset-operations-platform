"""
Excel import service for TAT inventory exports.

Column mapping strategy
-----------------------
TAT doesn't always export consistent column names, so we resolve columns
via a priority-ordered list of case-insensitive aliases per logical field.
The first alias found in the sheet header wins.

Logical fields and their known aliases:
  item_name     → "Item Name", "ItemName", "Description", ...
  serial_number → "Serial Number", "SerialNumber", "SN", ...
  part_number   → "Part Number", "PartNumber", "Part#", "PN", ...
  status        → "System Status", "Status", "Estado", ...
  location      → "Rig Location", "Location", "Ubicación", ...
  size          → "Size", "Tamaño"  (appended to item_name)
  internal_code → "Internal Code", "Code", "Código Interno", ...

Transaction strategy
--------------------
Each row is flushed individually with a per-row savepoint so that one bad
row never rolls back the entire import.  A final db.commit() persists all
successful rows in a single transaction.
"""

import re
from io import BytesIO
from typing import Any

import openpyxl
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetStatus
from app.models.part import Part
from app.schemas.excel_import import (
    ColumnMapping, ImportResult, ImportRowError,
)


# ── Constants ──────────────────────────────────────────────────────────────────

MAX_ERRORS_PER_IMPORT = 500
MAX_ROWS_PER_IMPORT   = 10_000
MAX_FIELD_LEN         = 255

# ── Column alias registry ──────────────────────────────────────────────────────

COLUMN_ALIASES: dict[str, list[str]] = {
    "item_name": [
        "item name", "itemname", "item_name",
        "description", "descripcion", "descripción",
        "equipment name", "nombre", "nombre equipo",
    ],
    "serial_number": [
        "serial number", "serialnumber", "serial_number",
        "serial no", "serial no.", "serial#", "sn",
        "numero de serie", "nro serie", "nro. serie",
    ],
    "part_number": [
        "part number", "partnumber", "part_number",
        "part#", "part no", "part no.",
        "numero de parte", "nro parte", "nro. parte", "pn",
    ],
    "status": [
        "system status", "systemstatus", "system_status",
        "status", "asset status", "estado", "estado equipo",
    ],
    "location": [
        "rig location", "riglocation", "rig_location",
        "location", "ubicacion", "ubicación", "rig loc",
    ],
    "size": ["size", "tamaño", "tamano"],
    "internal_code": [
        "internal code", "internalcode", "internal_code",
        "code", "asset code", "codigo interno", "código interno",
        "int code", "int. code",
    ],
}

# Status normalisation: lowercase Excel value → AssetStatus
STATUS_MAP: dict[str, AssetStatus] = {
    "active":        AssetStatus.IN_USE,
    "activo":        AssetStatus.IN_USE,
    "in use":        AssetStatus.IN_USE,
    "in_use":        AssetStatus.IN_USE,
    "inuse":         AssetStatus.IN_USE,
    "en uso":        AssetStatus.IN_USE,
    "available":     AssetStatus.AVAILABLE,
    "disponible":    AssetStatus.AVAILABLE,
    "libre":         AssetStatus.AVAILABLE,
    "maintenance":   AssetStatus.MAINTENANCE,
    "mantenimiento": AssetStatus.MAINTENANCE,
    "retired":       AssetStatus.RETIRED,
    "retirado":      AssetStatus.RETIRED,
    "baja":          AssetStatus.RETIRED,
    "inactive":      AssetStatus.RETIRED,
    "inactivo":      AssetStatus.RETIRED,
    "unknown":       AssetStatus.UNKNOWN,
    "desconocido":   AssetStatus.UNKNOWN,
}


# ── Cell helpers ───────────────────────────────────────────────────────────────

def _str(value: Any, max_len: int = MAX_FIELD_LEN) -> str | None:
    """Coerce cell value to a clean string, or None if blank."""
    if value is None:
        return None
    s = re.sub(r"\s+", " ", str(value).strip())
    return s[:max_len] if s else None


def _normalise_status(value: Any) -> AssetStatus:
    v = _str(value)
    return STATUS_MAP.get(v.lower() if v else "", AssetStatus.UNKNOWN)


# ── Column resolver ────────────────────────────────────────────────────────────

def _resolve_columns(
    headers: list[str],
) -> tuple[dict[str, int], ColumnMapping, list[str]]:
    """
    Returns:
      col_map            — {logical_field: col_index}  (0-based)
      detected_columns   — human-readable ColumnMapping for the response
      unrecognised       — header strings not matched to any field
    """
    normalised = [h.lower().strip() if h else "" for h in headers]
    col_map: dict[str, int] = {}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            try:
                col_map[field] = normalised.index(alias)
                break
            except ValueError:
                continue

    detected = ColumnMapping(**{
        field: headers[idx]
        for field, idx in col_map.items()
        if idx < len(headers)
    })

    # Headers that didn't match any alias
    matched_indices = set(col_map.values())
    unrecognised = [
        h for i, h in enumerate(headers)
        if i not in matched_indices and h.strip()
    ]

    return col_map, detected, unrecognised


def _get(row: tuple, col_map: dict[str, int], field: str) -> Any:
    idx = col_map.get(field)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


# ── Part upsert ────────────────────────────────────────────────────────────────

def _upsert_part(
    db: Session,
    part_number: str,
    description: str | None,
    cache: dict[str, Part],
) -> tuple[Part, bool]:
    """Get-or-create a Part.  Uses in-memory cache to avoid repeated DB hits."""
    key = part_number.upper()
    if key in cache:
        return cache[key], False

    part = db.query(Part).filter(Part.part_number == part_number).first()
    if part:
        cache[key] = part
        return part, False

    part = Part(part_number=part_number, description=description)
    db.add(part)
    db.flush()
    cache[key] = part
    return part, True


# ── Asset upsert ───────────────────────────────────────────────────────────────

def _upsert_asset(
    db: Session,
    part: Part,
    serial_number: str | None,
    internal_code: str | None,
    item_name: str,
    status: AssetStatus,
    location: str | None,
    sn_cache: dict[str, Asset],
    ic_cache: dict[str, Asset],
) -> tuple[Asset, str]:
    """
    Returns (Asset, action) where action ∈ {"created", "updated", "skipped"}.
    Lookup priority: serial_number → internal_code.
    """
    existing: Asset | None = None

    if serial_number:
        existing = sn_cache.get(serial_number.upper()) or (
            db.query(Asset).filter(Asset.serial_number == serial_number).first()
        )

    if not existing and internal_code:
        existing = ic_cache.get(internal_code.upper()) or (
            db.query(Asset).filter(Asset.internal_code == internal_code).first()
        )

    if existing:
        changed = False
        updates = {
            "item_name": item_name,
            "part_id":   part.id,
            **({"status": status} if status != AssetStatus.UNKNOWN else {}),
            **({"location": location} if location else {}),
        }
        for attr, new_val in updates.items():
            if getattr(existing, attr) != new_val:
                setattr(existing, attr, new_val)
                changed = True
        if changed:
            db.flush()
        return existing, "updated" if changed else "skipped"

    # Create
    asset = Asset(
        part_id=part.id,
        serial_number=serial_number,
        internal_code=internal_code,
        item_name=item_name,
        status=status,
        location=location,
    )
    db.add(asset)
    db.flush()

    if serial_number:
        sn_cache[serial_number.upper()] = asset
    if internal_code:
        ic_cache[internal_code.upper()] = asset

    return asset, "created"


# ── Main public function ───────────────────────────────────────────────────────

def import_excel(
    db: Session,
    file_bytes: bytes,
    filename: str,
    sheet_name: str | None = None,
) -> ImportResult:
    """
    Parse an .xlsx file and upsert Parts + Assets into the database.

    Each row is processed inside an individual SAVEPOINT so that a bad row
    never rolls back successful rows.  All work is committed at the end.

    Raises:
        ValueError  — unreadable file, sheet not found, or fatal parse error.
        RuntimeError — final commit failed.
    """
    # ── 1. Open workbook ───────────────────────────────────────────────────────
    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"No se pudo abrir el archivo Excel: {exc}") from exc

    available_sheets = wb.sheetnames

    if sheet_name:
        if sheet_name not in available_sheets:
            raise ValueError(
                f"Hoja '{sheet_name}' no encontrada. "
                f"Hojas disponibles: {', '.join(available_sheets)}"
            )
        ws = wb[sheet_name]
    else:
        ws = wb.active

    actual_sheet = ws.title

    # ── 2. Read rows ───────────────────────────────────────────────────────────
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not all_rows:
        return ImportResult(
            filename=filename,
            sheet=actual_sheet,
            available_sheets=available_sheets,
        )

    # ── 3. Resolve columns from header row ─────────────────────────────────────
    header_raw = [str(c).strip() if c is not None else "" for c in all_rows[0]]
    col_map, detected_columns, unrecognised = _resolve_columns(header_raw)

    data_rows = all_rows[1:]
    if len(data_rows) > MAX_ROWS_PER_IMPORT:
        data_rows = data_rows[:MAX_ROWS_PER_IMPORT]

    # ── 4. Initialise result ───────────────────────────────────────────────────
    result = ImportResult(
        filename=filename,
        sheet=actual_sheet,
        available_sheets=available_sheets,
        detected_columns=detected_columns,
        unrecognised_columns=unrecognised,
        total_rows=0,   # incremented only for non-empty rows
    )

    part_cache: dict[str, Part]  = {}
    sn_cache:   dict[str, Asset] = {}
    ic_cache:   dict[str, Asset] = {}

    # ── 5. Process each row ────────────────────────────────────────────────────
    for raw_idx, row in enumerate(data_rows):
        excel_row = raw_idx + 2   # +1 header, +1 Excel 1-based

        # Skip blank rows silently
        if all(c is None or str(c).strip() == "" for c in row):
            continue

        result.total_rows += 1

        if len(result.errors) >= MAX_ERRORS_PER_IMPORT:
            break

        # ── Extract & normalise ────────────────────────────────────────────────
        raw_pn    = _str(_get(row, col_map, "part_number"))
        raw_sn    = _str(_get(row, col_map, "serial_number"))
        raw_ic    = _str(_get(row, col_map, "internal_code"))
        raw_name  = _str(_get(row, col_map, "item_name"))
        raw_size  = _str(_get(row, col_map, "size"))
        raw_loc   = _str(_get(row, col_map, "location"))
        raw_stat  = _get(row, col_map, "status")

        # part_number → uppercase, no internal spaces
        part_number = re.sub(r"\s+", "", raw_pn).upper() if raw_pn else None

        # identifiers → uppercase for consistent matching
        serial_number = raw_sn.upper() if raw_sn else None
        internal_code = raw_ic.upper() if raw_ic else None

        # Build item_name; append size suffix if useful
        item_name = raw_name or "Sin nombre"
        if raw_size and raw_size.lower() not in item_name.lower():
            item_name = f"{item_name} ({raw_size})"
        item_name = item_name[:MAX_FIELD_LEN]

        status   = _normalise_status(raw_stat)
        location = raw_loc[:MAX_FIELD_LEN] if raw_loc else None
        identifier = serial_number or internal_code

        # ── Validate required fields ───────────────────────────────────────────
        if not part_number:
            result.errors.append(ImportRowError(
                row=excel_row,
                identifier=identifier,
                reason="Campo 'Part Number' vacío o columna no detectada en este archivo.",
            ))
            result.rows_skipped += 1
            continue

        if not serial_number and not internal_code:
            result.errors.append(ImportRowError(
                row=excel_row,
                identifier=None,
                reason=(
                    "Se requiere al menos 'Serial Number' o 'Internal Code'. "
                    "Ambos están vacíos en esta fila."
                ),
            ))
            result.rows_skipped += 1
            continue

        # ── Upsert Part (with per-row savepoint) ───────────────────────────────
        savepoint = db.begin_nested()
        try:
            part, part_created = _upsert_part(
                db, part_number,
                description=raw_name,
                cache=part_cache,
            )
        except Exception as exc:
            savepoint.rollback()
            result.errors.append(ImportRowError(
                row=excel_row,
                identifier=identifier,
                reason=f"Error al crear Part '{part_number}': {exc}",
            ))
            result.rows_skipped += 1
            continue
        else:
            savepoint.commit()
            if part_created:
                result.parts_created += 1
            else:
                result.parts_reused += 1

        # ── Upsert Asset (with per-row savepoint) ──────────────────────────────
        savepoint = db.begin_nested()
        try:
            _asset, action = _upsert_asset(
                db, part,
                serial_number=serial_number,
                internal_code=internal_code,
                item_name=item_name,
                status=status,
                location=location,
                sn_cache=sn_cache,
                ic_cache=ic_cache,
            )
        except IntegrityError as exc:
            savepoint.rollback()
            result.errors.append(ImportRowError(
                row=excel_row,
                identifier=identifier,
                reason=(
                    f"Conflicto de unicidad al guardar Asset "
                    f"(serial/code ya existe con otro registro): {exc.orig}"
                ),
            ))
            result.rows_skipped += 1
            continue
        except Exception as exc:
            savepoint.rollback()
            result.errors.append(ImportRowError(
                row=excel_row,
                identifier=identifier,
                reason=f"Error inesperado al crear/actualizar Asset: {exc}",
            ))
            result.rows_skipped += 1
            continue
        else:
            savepoint.commit()
            if action == "created":
                result.assets_created += 1
            elif action == "updated":
                result.assets_updated += 1
            else:
                result.rows_skipped += 1   # "skipped" = no changes detected

    # ── 6. Final commit ────────────────────────────────────────────────────────
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise RuntimeError(
            f"Error al confirmar la importación en la base de datos: {exc}"
        ) from exc

    return result
