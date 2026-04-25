from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.intervention import Intervention, InterventionAsset
from app.schemas.intervention import (
    InterventionCreate, InterventionUpdate, InterventionAssetCreate,
)
from app.services.exceptions import not_found, conflict, bad_request
from app.services.asset_service import get_asset_or_404


def _load_full(db: Session, intervention_id: int) -> Intervention:
    """Load an intervention with all nested relations eagerly."""
    intervention = (
        db.query(Intervention)
        .options(
            selectinload(Intervention.intervention_assets).joinedload(
                InterventionAsset.asset
            ).joinedload("part"),
            selectinload(Intervention.evidences),
        )
        .filter(Intervention.id == intervention_id)
        .first()
    )
    if not intervention:
        raise not_found("Intervention", intervention_id)
    return intervention


def get_intervention_or_404(db: Session, intervention_id: int) -> Intervention:
    return _load_full(db, intervention_id)


def create_intervention(db: Session, data: InterventionCreate) -> Intervention:
    intervention = Intervention(**data.model_dump())
    db.add(intervention)
    db.commit()
    db.refresh(intervention)
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

    total = q.count()
    items = q.order_by(Intervention.date.desc()).offset(skip).limit(limit).all()
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

    db.commit()
    return _load_full(db, intervention_id)


def add_asset_to_intervention(
    db: Session, intervention_id: int, data: InterventionAssetCreate
) -> InterventionAsset:
    # Both must exist
    intervention = get_intervention_or_404(db, intervention_id)
    asset = get_asset_or_404(db, data.asset_id)

    # Prevent duplicate association
    existing = (
        db.query(InterventionAsset)
        .filter(
            InterventionAsset.intervention_id == intervention_id,
            InterventionAsset.asset_id == data.asset_id,
        )
        .first()
    )
    if existing:
        raise conflict(
            f"El asset id={data.asset_id} ya está asociado "
            f"a la intervención id={intervention_id}."
        )

    ia = InterventionAsset(
        intervention_id=intervention_id,
        asset_id=data.asset_id,
        notes=data.notes,
    )
    db.add(ia)
    db.commit()

    # Reload with nested asset + part
    ia_loaded = (
        db.query(InterventionAsset)
        .options(
            joinedload(InterventionAsset.asset).joinedload("part")
        )
        .filter(InterventionAsset.id == ia.id)
        .first()
    )
    return ia_loaded
