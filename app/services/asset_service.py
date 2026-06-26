import logging

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.asset import Asset
from app.models.intervention import Evidence, Intervention, InterventionAsset
from app.schemas.asset import AssetCreate, AssetHistoryItem, AssetUpdate
from app.services.exceptions import not_found, conflict, bad_request, service_unavailable
from app.services.part_service import get_part_or_404

logger = logging.getLogger(__name__)


def get_asset_or_404(db: Session, asset_id: int) -> Asset:
    try:
        asset = (
            db.query(Asset)
            .options(joinedload(Asset.part))
            .filter(Asset.id == asset_id)
            .first()
        )
    except SQLAlchemyError:
        logger.exception("Database error loading asset", extra={"asset_id": asset_id})
        raise service_unavailable("No fue posible consultar el asset en este momento.")
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
        logger.warning("Asset create conflict", extra={"serial_number": data.serial_number, "internal_code": data.internal_code})
        raise conflict("serial_number o internal_code ya existe en otro registro.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating asset")
        raise service_unavailable("No fue posible registrar el asset en este momento.")

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

    try:
        total = q.count()
        items = q.order_by(
            Asset.item_name.asc(),
            Asset.serial_number.asc(),
            Asset.id.asc()
        ).offset(skip).limit(limit).all()
    except SQLAlchemyError:
        logger.exception("Database error listing assets", extra={"skip": skip, "limit": limit})
        raise service_unavailable("No fue posible listar los assets en este momento.")
    
    return total, items


def _build_intervention_history_title(intervention: Intervention) -> str:
    return f"{intervention.type.value.replace('_', ' ').title()} - {intervention.rig} / {intervention.pozo}"


def list_asset_history(
    db: Session,
    asset_id: int,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[AssetHistoryItem]]:
    get_asset_or_404(db, asset_id)

    evidence_counts = (
        db.query(
            Evidence.intervention_id.label("intervention_id"),
            func.count(Evidence.id).label("evidence_count"),
        )
        .group_by(Evidence.intervention_id)
        .subquery()
    )

    q = (
        db.query(
            Intervention,
            func.coalesce(evidence_counts.c.evidence_count, 0).label("evidence_count"),
        )
        .join(InterventionAsset, InterventionAsset.intervention_id == Intervention.id)
        .outerjoin(evidence_counts, evidence_counts.c.intervention_id == Intervention.id)
        .filter(InterventionAsset.asset_id == asset_id)
    )

    try:
        total = q.count()
        rows = (
            q.order_by(Intervention.created_at.desc(), Intervention.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error listing asset history", extra={"asset_id": asset_id})
        raise service_unavailable("No fue posible consultar el historial del asset en este momento.")

    items = [
        AssetHistoryItem(
            intervention_id=intervention.id,
            title=_build_intervention_history_title(intervention),
            status="closed" if intervention.end_date else "open",
            created_at=intervention.created_at,
            closed_at=intervention.end_date,
            associated_technician=intervention.technician,
            evidence_count=int(evidence_count or 0),
        )
        for intervention, evidence_count in rows
    ]
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
        logger.warning("Asset update conflict", extra={"asset_id": asset_id})
        raise conflict("serial_number o internal_code ya existe en otro registro.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error updating asset", extra={"asset_id": asset_id})
        raise service_unavailable("No fue posible actualizar el asset en este momento.")

    return get_asset_or_404(db, asset_id)
