import logging
from collections.abc import Mapping

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    *,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    metadata: Mapping | None = None,
) -> None:
    """
    Best-effort audit log.

    Uses an independent DB session so audit failures never affect
    the main business transaction.
    """
    db = SessionLocal()
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=dict(metadata) if metadata else None,
        )
        db.add(entry)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.warning(
            "Audit log write failed",
            extra={
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
            exc_info=True,
        )
    except Exception:
        logger.warning(
            "Unexpected audit log failure",
            extra={
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
            },
            exc_info=True,
        )
    finally:
        db.close()
