import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.asset import Asset
from app.models.intervention import Intervention, InterventionAsset
from app.schemas.intervention import (
    InterventionCreate, InterventionUpdate, InterventionAssetCreate,
)
from app.services.exceptions import not_found, conflict, bad_request, service_unavailable
from app.services.asset_service import get_asset_or_404

logger = logging.getLogger(__name__)


def _load_full(db: Session, intervention_id: int) -> Intervention:
    """Load an intervention with all nested relations eagerly."""
    try:
        intervention = (
            db.query(Intervention)
            .options(
                selectinload(Intervention.intervention_assets).joinedload(
                    InterventionAsset.asset
                ).joinedload(Asset.part),
                selectinload(Intervention.evidences),
            )
            .filter(Intervention.id == intervention_id)
            .first()
        )
    except SQLAlchemyError:
        logger.exception("Database error loading intervention", extra={"intervention_id": intervention_id})
        raise service_unavailable("No fue posible consultar la intervención en este momento.")
    if not intervention:
        raise not_found("Intervention", intervention_id)
    return intervention


def get_intervention_or_404(db: Session, intervention_id: int) -> Intervention:
    return _load_full(db, intervention_id)


def create_intervention(db: Session, data: InterventionCreate) -> Intervention:
    intervention = Intervention(**data.model_dump())
    db.add(intervention)
    try:
        db.commit()
        db.refresh(intervention)
    except IntegrityError:
        db.rollback()
        logger.warning("Intervention create conflict", extra={"rig": data.rig, "pozo": data.pozo})
        raise bad_request("No fue posible crear la intervención con los datos enviados.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating intervention")
        raise service_unavailable("No fue posible crear la intervención en este momento.")

    logger.info(
        "Intervention created",
        extra={"intervention_id": intervention.id, "rig": intervention.rig, "pozo": intervention.pozo},
    )
    return _load_full(db, intervention.id)


def list_interventions(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    rig: str | None = None,
    pozo: str | None = None,
    technician: str | None = None,
    type: str | None = None,
) -> tuple[int, list[Intervention]]:
    q = (
        db.query(Intervention)
        .options(
            selectinload(Intervention.intervention_assets),
            selectinload(Intervention.evidences),
        )
    )
    if rig:
        q = q.filter(Intervention.rig.ilike(f"%{rig}%"))
    if pozo:
        q = q.filter(Intervention.pozo.ilike(f"%{pozo}%"))
    if technician:
        q = q.filter(Intervention.technician.ilike(f"%{technician}%"))
    if type:
        q = q.filter(Intervention.type == type)

    try:
        total = q.count()
        items = q.order_by(Intervention.date.desc(), Intervention.id.desc()).offset(skip).limit(limit).all()
    except SQLAlchemyError:
        logger.exception("Database error listing interventions", extra={"skip": skip, "limit": limit})
        raise service_unavailable("No fue posible listar las intervenciones en este momento.")
    return total, items


def update_intervention(
    db: Session, intervention_id: int, data: InterventionUpdate
) -> Intervention:
    intervention = get_intervention_or_404(db, intervention_id)

    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return intervention

    for field, value in patch.items():
        setattr(intervention, field, value)

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error updating intervention", extra={"intervention_id": intervention_id})
        raise service_unavailable("No fue posible actualizar la intervención en este momento.")
    return _load_full(db, intervention_id)


def add_asset_to_intervention(
    db: Session, intervention_id: int, data: InterventionAssetCreate
) -> InterventionAsset:
    # Both must exist
    get_intervention_or_404(db, intervention_id)
    get_asset_or_404(db, data.asset_id)

    # Prevent duplicate association
    try:
        existing = (
            db.query(InterventionAsset)
            .filter(
                InterventionAsset.intervention_id == intervention_id,
                InterventionAsset.asset_id == data.asset_id,
            )
            .first()
        )
    except SQLAlchemyError:
        logger.exception(
            "Database error checking intervention asset association",
            extra={"intervention_id": intervention_id, "asset_id": data.asset_id},
        )
        raise service_unavailable("No fue posible asociar el asset en este momento.")
    if existing:
        raise conflict(
            f"El asset id={data.asset_id} ya está asociado "
            f"a la intervención id={intervention_id}."
        )

    ia = InterventionAsset(
        intervention_id=intervention_id,
        asset_id=data.asset_id,
        location_note=data.location_note,
        notes=data.notes,
    )
    db.add(ia)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Duplicate intervention asset association",
            extra={"intervention_id": intervention_id, "asset_id": data.asset_id},
        )
        raise conflict(
            f"El asset id={data.asset_id} ya está asociado "
            f"a la intervención id={intervention_id}."
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error adding asset to intervention",
            extra={"intervention_id": intervention_id, "asset_id": data.asset_id},
        )
        raise service_unavailable("No fue posible asociar el asset en este momento.")

    # Reload with nested asset + part
    try:
        ia_loaded = (
            db.query(InterventionAsset)
            .options(
                joinedload(InterventionAsset.asset).joinedload(Asset.part)
            )
            .filter(InterventionAsset.id == ia.id)
            .first()
        )
    except SQLAlchemyError:
        logger.exception(
            "Database error reloading intervention asset",
            extra={"intervention_asset_id": ia.id},
        )
        raise service_unavailable("La asociación fue creada, pero no pudo cargarse correctamente.")
    logger.info(
        "Asset associated to intervention",
        extra={"intervention_id": intervention_id, "asset_id": data.asset_id},
    )
    return ia_loaded
