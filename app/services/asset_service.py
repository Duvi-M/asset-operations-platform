from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services.exceptions import not_found, conflict, bad_request
from app.services.part_service import get_part_or_404


def get_asset_or_404(db: Session, asset_id: int) -> Asset:
    asset = (
        db.query(Asset)
        .options(joinedload(Asset.part))
        .filter(Asset.id == asset_id)
        .first()
    )
    if not asset:
        raise not_found("Asset", asset_id)
    return asset


def _check_serial_unique(db: Session, serial: str, exclude_id: int | None = None) -> None:
    q = db.query(Asset).filter(Asset.serial_number == serial)
    if exclude_id:
        q = q.filter(Asset.id != exclude_id)
    if q.first():
        raise conflict(f"Ya existe un Asset con serial_number='{serial}'.")


def _check_internal_code_unique(db: Session, code: str, exclude_id: int | None = None) -> None:
    q = db.query(Asset).filter(Asset.internal_code == code)
    if exclude_id:
        q = q.filter(Asset.id != exclude_id)
    if q.first():
        raise conflict(f"Ya existe un Asset con internal_code='{code}'.")


def create_asset(db: Session, data: AssetCreate) -> Asset:
    # Validate referenced part exists
    get_part_or_404(db, data.part_id)

    # Uniqueness checks before insert
    if data.serial_number:
        _check_serial_unique(db, data.serial_number)
    if data.internal_code:
        _check_internal_code_unique(db, data.internal_code)

    asset = Asset(**data.model_dump())
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("serial_number o internal_code ya existe en otro registro.")

    return get_asset_or_404(db, asset.id)


def list_assets(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    search: str | None = None,
    part_id: int | None = None,
) -> tuple[int, list[Asset]]:
    q = db.query(Asset).options(joinedload(Asset.part))

    if status:
        q = q.filter(Asset.status == status)
    if part_id:
        q = q.filter(Asset.part_id == part_id)
    if search:
        q = q.filter(
            Asset.item_name.ilike(f"%{search}%") |
            Asset.serial_number.ilike(f"%{search}%") |
            Asset.internal_code.ilike(f"%{search}%") |
            Asset.location.ilike(f"%{search}%")
        )

    total = q.count()
    items = q.order_by(
    Asset.item_name.asc(),
    Asset.serial_number.asc(),
    Asset.id.asc()
    ).offset(skip).limit(limit).all()
    
    return total, items


def update_asset(db: Session, asset_id: int, data: AssetUpdate) -> Asset:
    asset = get_asset_or_404(db, asset_id)

    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return asset

    # If updating part_id, verify part exists
    if "part_id" in patch:
        get_part_or_404(db, patch["part_id"])

    # Identifier uniqueness checks
    new_serial = patch.get("serial_number", asset.serial_number)
    new_code = patch.get("internal_code", asset.internal_code)

    if "serial_number" in patch and patch["serial_number"] is not None:
        _check_serial_unique(db, patch["serial_number"], exclude_id=asset_id)
    if "internal_code" in patch and patch["internal_code"] is not None:
        _check_internal_code_unique(db, patch["internal_code"], exclude_id=asset_id)

    # After applying patch, ensure at least one identifier remains
    if not new_serial and not new_code:
        raise bad_request(
            "El equipo debe conservar al menos un identificador: "
            "'serial_number' o 'internal_code'."
        )

    for field, value in patch.items():
        setattr(asset, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("serial_number o internal_code ya existe en otro registro.")

    return get_asset_or_404(db, asset_id)
