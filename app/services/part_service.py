import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.part import Part
from app.schemas.part import PartCreate, PartUpdate
from app.services.exceptions import not_found, conflict, service_unavailable

logger = logging.getLogger(__name__)


def get_part_or_404(db: Session, part_id: int) -> Part:
    try:
        part = db.get(Part, part_id)
    except SQLAlchemyError:
        logger.exception("Database error loading part", extra={"part_id": part_id})
        raise service_unavailable("No fue posible consultar el part en este momento.")
    if not part:
        raise not_found("Part", part_id)
    return part


def create_part(db: Session, data: PartCreate) -> Part:
    # Uniqueness check with a friendly error (DB constraint is the safety net)
    existing = db.query(Part).filter(Part.part_number == data.part_number).first()
    if existing:
        raise conflict(f"Ya existe un Part con part_number='{data.part_number}'.")

    part = Part(**data.model_dump())
    db.add(part)
    try:
        db.commit()
        db.refresh(part)
    except IntegrityError:
        db.rollback()
        logger.warning("Part create conflict", extra={"part_number": data.part_number})
        raise conflict(f"Ya existe un Part con part_number='{data.part_number}'.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating part")
        raise service_unavailable("No fue posible registrar el part en este momento.")
    return part


def list_parts(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
) -> tuple[int, list[Part]]:
    q = db.query(Part)
    if search:
        q = q.filter(
            Part.part_number.ilike(f"%{search}%") |
            Part.description.ilike(f"%{search}%")
        )
    try:
        total = q.count()
        items = q.order_by(Part.part_number).offset(skip).limit(limit).all()
    except SQLAlchemyError:
        logger.exception("Database error listing parts", extra={"skip": skip, "limit": limit})
        raise service_unavailable("No fue posible listar los parts en este momento.")
    return total, items


def update_part(db: Session, part_id: int, data: PartUpdate) -> Part:
    part = get_part_or_404(db, part_id)

    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return part

    # Uniqueness check if part_number is being changed
    if "part_number" in patch and patch["part_number"] != part.part_number:
        existing = db.query(Part).filter(Part.part_number == patch["part_number"]).first()
        if existing:
            raise conflict(f"Ya existe un Part con part_number='{patch['part_number']}'.")

    for field, value in patch.items():
        setattr(part, field, value)

    try:
        db.commit()
        db.refresh(part)
    except IntegrityError:
        db.rollback()
        raise conflict(f"Ya existe un Part con part_number='{patch.get('part_number')}'.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error updating part", extra={"part_id": part_id})
        raise service_unavailable("No fue posible actualizar el part en este momento.")
    return part
