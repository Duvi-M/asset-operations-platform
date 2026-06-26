import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.asset import Asset
from app.models.docs import (
    DocsDocument,
    DocsDocumentStatus,
    DocsFile,
    DocsItemReference,
    DocsReferenceType,
    DocsRelatedDocument,
    TechnicalItem,
    TechnicalItemDocument,
    TechnicalItemDocumentRelationType,
)
from app.schemas.docs import (
    DocsDocumentCreate,
    DocsDocumentUpdate,
    DocsItemReferenceCreate,
    DocsRelatedDocumentCreate,
    TechnicalItemCreate,
    TechnicalItemDocumentAttach,
    TechnicalItemUpdate,
)
from app.services import cloudinary_service
from app.services import audit_service
from app.services.exceptions import bad_request, conflict, not_found, service_unavailable

logger = logging.getLogger(__name__)

MAX_DOC_FILE_SIZE_MB = 50
MAX_DOC_FILE_SIZE_BYTES = MAX_DOC_FILE_SIZE_MB * 1024 * 1024

ALLOWED_DOC_MIME_TYPES = {
    "application/msword",
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/gif",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/plain",
}
ALLOWED_DOC_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".txt",
    ".webp",
    ".xls",
    ".xlsx",
}

SEARCHABLE_REFERENCE_TYPES = (
    DocsReferenceType.PART_NUMBER,
    DocsReferenceType.ITEM_ID,
    DocsReferenceType.SERIAL_NUMBER,
    DocsReferenceType.INTERNAL_CODE,
    DocsReferenceType.MANUFACTURER_CODE,
    DocsReferenceType.MODEL,
)

AUTO_LINK_REFERENCE_FIELDS = {
    DocsReferenceType.PART_NUMBER: "part_number",
    DocsReferenceType.ITEM_ID: "item_id",
    DocsReferenceType.MODEL: "model",
    DocsReferenceType.MANUFACTURER_CODE: "manufacturer_code",
}

TECHNICAL_PACKET_GROUPS = {
    TechnicalItemDocumentRelationType.MANUAL: "manuals",
    TechnicalItemDocumentRelationType.CERTIFICATE: "certificates",
    TechnicalItemDocumentRelationType.DIAGRAM: "diagrams",
    TechnicalItemDocumentRelationType.PROCEDURE: "procedures",
    TechnicalItemDocumentRelationType.DATASHEET: "datasheets",
    TechnicalItemDocumentRelationType.REPORT: "reports",
    TechnicalItemDocumentRelationType.RELATED: "related",
}


def normalize_reference_value(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.strip().upper())


def normalize_search_text(value: str) -> str:
    return value.strip().lower()


def compact_search_value(value: str) -> str:
    return re.sub(r"[\s\-_]+", "", normalize_search_text(value))


def normalize_technical_identifier(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[\s\-_]+", "", value.strip().lower())


def _compact_column(column):
    return func.replace(
        func.replace(
            func.replace(func.lower(func.coalesce(column, "")), " ", ""),
            "-",
            "",
        ),
        "_",
        "",
    )


def _docs_upload_dir(document_id: int) -> Path:
    path = Path(settings.media_dir) / "docs" / str(document_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _document_query(db: Session):
    return db.query(DocsDocument).options(
        joinedload(DocsDocument.file),
        joinedload(DocsDocument.item_references),
        joinedload(DocsDocument.related_out).joinedload(DocsRelatedDocument.related_document),
    )


def _technical_item_query(db: Session):
    return db.query(TechnicalItem).options(
        joinedload(TechnicalItem.documents).joinedload(TechnicalItemDocument.document),
    )


def get_document_or_404(db: Session, document_id: int) -> DocsDocument:
    try:
        document = _document_query(db).filter(DocsDocument.id == document_id).first()
    except SQLAlchemyError:
        logger.exception("Database error loading docs document", extra={"document_id": document_id})
        raise service_unavailable("No fue posible consultar el documento en este momento.")
    if not document:
        raise not_found("DocsDocument", document_id)
    return document


def ensure_document_visible(document: DocsDocument, is_admin: bool) -> None:
    if is_admin:
        return
    if document.status != DocsDocumentStatus.ACTIVE:
        raise not_found("DocsDocument", document.id)


def _check_document_code_unique(db: Session, document_code: str, exclude_id: int | None = None) -> None:
    q = db.query(DocsDocument).filter(DocsDocument.document_code == document_code)
    if exclude_id:
        q = q.filter(DocsDocument.id != exclude_id)
    if q.first():
        raise conflict(f"Ya existe un documento con document_code='{document_code}'.")


def _check_technical_item_id_unique(db: Session, item_id: str, exclude_id: int | None = None) -> None:
    q = db.query(TechnicalItem).filter(TechnicalItem.item_id == item_id)
    if exclude_id:
        q = q.filter(TechnicalItem.id != exclude_id)
    if q.first():
        raise conflict(f"Ya existe un technical item con item_id='{item_id}'.")


def _reference_from_payload(document_id: int, data: DocsItemReferenceCreate) -> DocsItemReference:
    normalized = normalize_reference_value(data.reference_value)
    if not normalized:
        raise bad_request("reference_value debe contener al menos un carácter alfanumérico.")
    return DocsItemReference(
        document_id=document_id,
        reference_type=data.reference_type,
        reference_value=data.reference_value,
        normalized_value=normalized,
        label=data.label,
    )


def _infer_technical_item_relation_type(document_type: str | None) -> TechnicalItemDocumentRelationType:
    value = normalize_technical_identifier(document_type)
    if "manual" in value:
        return TechnicalItemDocumentRelationType.MANUAL
    if "certificate" in value or "certificado" in value:
        return TechnicalItemDocumentRelationType.CERTIFICATE
    if "diagram" in value or "drawing" in value or "plano" in value:
        return TechnicalItemDocumentRelationType.DIAGRAM
    if "procedure" in value or "procedimiento" in value:
        return TechnicalItemDocumentRelationType.PROCEDURE
    if "datasheet" in value or "fichatecnica" in value:
        return TechnicalItemDocumentRelationType.DATASHEET
    if "report" in value or "informe" in value:
        return TechnicalItemDocumentRelationType.REPORT
    return TechnicalItemDocumentRelationType.RELATED


def _technical_item_identifier_map(item: TechnicalItem) -> dict[DocsReferenceType, str]:
    return {
        DocsReferenceType.PART_NUMBER: normalize_technical_identifier(item.part_number),
        DocsReferenceType.ITEM_ID: normalize_technical_identifier(item.item_id),
        DocsReferenceType.MODEL: normalize_technical_identifier(item.model),
        DocsReferenceType.MANUFACTURER_CODE: normalize_technical_identifier(item.manufacturer_code),
    }


def _technical_item_query_identifier_map(item: TechnicalItem) -> dict[str, str]:
    return {
        "part_number": normalize_technical_identifier(item.part_number),
        "item_id": normalize_technical_identifier(item.item_id),
        "model": normalize_technical_identifier(item.model),
        "manufacturer_code": normalize_technical_identifier(item.manufacturer_code),
    }


def _document_reference_map(document: DocsDocument) -> dict[DocsReferenceType, set[str]]:
    values: dict[DocsReferenceType, set[str]] = {reference_type: set() for reference_type in AUTO_LINK_REFERENCE_FIELDS}
    for reference in document.item_references:
        if reference.reference_type not in AUTO_LINK_REFERENCE_FIELDS:
            continue
        normalized = normalize_technical_identifier(reference.reference_value)
        if normalized:
            values[reference.reference_type].add(normalized)
    return values


def _matching_technical_items_for_document(db: Session, document: DocsDocument) -> list[tuple[TechnicalItem, DocsReferenceType]]:
    reference_values = _document_reference_map(document)
    if not any(reference_values.values()):
        return []

    try:
        items = db.query(TechnicalItem).all()
    except SQLAlchemyError:
        logger.exception("Database error finding technical items for docs document", extra={"document_id": document.id})
        raise service_unavailable("No fue posible vincular el documento con technical items en este momento.")

    matches: list[tuple[TechnicalItem, DocsReferenceType]] = []
    for item in items:
        item_values = _technical_item_identifier_map(item)
        for reference_type, values in reference_values.items():
            if item_values.get(reference_type) and item_values[reference_type] in values:
                matches.append((item, reference_type))
                break
    return matches


def auto_link_document_to_technical_items(
    db: Session,
    document_id: int,
    *,
    actor_user_id: int | None = None,
) -> list[TechnicalItemDocument]:
    document = get_document_or_404(db, document_id)
    relation_type = _infer_technical_item_relation_type(document.document_type)
    matches = _matching_technical_items_for_document(db, document)
    created_links: list[TechnicalItemDocument] = []

    for item, matched_reference_type in matches:
        existing = (
            db.query(TechnicalItemDocument)
            .filter(
                TechnicalItemDocument.technical_item_id == item.id,
                TechnicalItemDocument.document_id == document.id,
                TechnicalItemDocument.relation_type == relation_type,
            )
            .first()
        )
        if existing:
            continue
        db.add(
            TechnicalItemDocument(
                technical_item_id=item.id,
                document_id=document.id,
                relation_type=relation_type,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "Database error auto-linking docs document to technical item",
                extra={"document_id": document.id, "technical_item_id": item.id},
            )
            raise service_unavailable("No fue posible vincular automáticamente el documento en este momento.")

        link = (
            db.query(TechnicalItemDocument)
            .options(joinedload(TechnicalItemDocument.document))
            .filter(
                TechnicalItemDocument.technical_item_id == item.id,
                TechnicalItemDocument.document_id == document.id,
                TechnicalItemDocument.relation_type == relation_type,
            )
            .first()
        )
        if link:
            created_links.append(link)
            audit_service.log_action(
                user_id=actor_user_id,
                action="auto_link_document_to_item",
                entity_type="technical_item",
                entity_id=item.id,
                metadata={
                    "document_id": document.id,
                    "document_code": document.document_code,
                    "relation_type": relation_type.value,
                    "matched_reference_type": matched_reference_type.value,
                },
            )

    return created_links


def _auto_link_technical_item_to_documents(
    db: Session,
    technical_item_id: int,
    *,
    actor_user_id: int | None = None,
) -> list[TechnicalItemDocument]:
    item = get_technical_item_or_404(db, technical_item_id)
    item_values = _technical_item_identifier_map(item)
    item_values = {reference_type: value for reference_type, value in item_values.items() if value}
    if not item_values:
        return []

    try:
        documents = (
            db.query(DocsDocument)
            .options(joinedload(DocsDocument.item_references))
            .join(DocsItemReference)
            .filter(DocsItemReference.reference_type.in_(tuple(item_values.keys())))
            .distinct()
            .all()
        )
    except SQLAlchemyError:
        logger.exception(
            "Database error finding docs documents for technical item",
            extra={"technical_item_id": technical_item_id},
        )
        raise service_unavailable("No fue posible vincular technical item con documentos en este momento.")

    created_links: list[TechnicalItemDocument] = []
    for document in documents:
        document_values = _document_reference_map(document)
        if any(item_values[reference_type] in document_values[reference_type] for reference_type in item_values):
            created_links.extend(
                auto_link_document_to_technical_items(
                    db,
                    document.id,
                    actor_user_id=actor_user_id,
                )
            )
    return created_links


def _run_document_auto_link_trigger(
    db: Session,
    document_id: int,
    *,
    actor_user_id: int | None = None,
) -> None:
    try:
        auto_link_document_to_technical_items(db, document_id, actor_user_id=actor_user_id)
    except Exception:
        logger.warning(
            "Docs document auto-link trigger failed",
            extra={"document_id": document_id},
            exc_info=True,
        )


def _run_technical_item_auto_link_trigger(
    db: Session,
    technical_item_id: int,
    *,
    actor_user_id: int | None = None,
) -> None:
    try:
        _auto_link_technical_item_to_documents(db, technical_item_id, actor_user_id=actor_user_id)
    except Exception:
        logger.warning(
            "Technical item auto-link trigger failed",
            extra={"technical_item_id": technical_item_id},
            exc_info=True,
        )


def _resolve_asset_identifiers(db: Session, asset_id: int | None) -> dict[str, str]:
    if asset_id is None:
        return {}
    try:
        asset = db.query(Asset).options(joinedload(Asset.part)).filter(Asset.id == asset_id).first()
    except SQLAlchemyError:
        logger.exception("Database error resolving asset for technical item lookup", extra={"asset_id": asset_id})
        raise service_unavailable("No fue posible resolver el activo para buscar documentos técnicos.")
    if not asset:
        raise not_found("Asset", asset_id)

    identifiers: dict[str, str] = {}
    if asset.part and asset.part.part_number:
        identifiers["part_number"] = asset.part.part_number
    if asset.serial_number:
        identifiers["serial_number"] = asset.serial_number
    if asset.internal_code:
        identifiers["internal_code"] = asset.internal_code
    if asset.item_name:
        identifiers["model"] = asset.item_name
    return identifiers


def _reference_type_for_query_field(field: str) -> DocsReferenceType | None:
    return {
        "part_number": DocsReferenceType.PART_NUMBER,
        "item_id": DocsReferenceType.ITEM_ID,
        "serial_number": DocsReferenceType.SERIAL_NUMBER,
        "internal_code": DocsReferenceType.INTERNAL_CODE,
        "model": DocsReferenceType.MODEL,
        "manufacturer_code": DocsReferenceType.MANUFACTURER_CODE,
    }.get(field)


def _score_direct_identifier_match(field: str, query_value: str, item_value: str) -> int:
    if not query_value or not item_value:
        return 0
    if query_value == item_value:
        if field == "part_number":
            return 100
        if field == "item_id":
            return 95
        if field in {"model", "manufacturer_code"}:
            return 85
        return 70
    if query_value in item_value or item_value in query_value:
        if field == "part_number":
            return 60
        if field == "item_id":
            return 55
        if field in {"model", "manufacturer_code"}:
            return 50
        return 35
    return 0


def _score_reference_identifier_match(
    db: Session,
    *,
    item_id: int,
    field: str,
    query_value: str,
) -> int:
    reference_type = _reference_type_for_query_field(field)
    if not reference_type or not query_value:
        return 0

    try:
        references = (
            db.query(DocsItemReference)
            .join(DocsDocument)
            .join(TechnicalItemDocument, TechnicalItemDocument.document_id == DocsDocument.id)
            .filter(
                TechnicalItemDocument.technical_item_id == item_id,
                DocsItemReference.reference_type == reference_type,
            )
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error scoring technical item reference match", extra={"technical_item_id": item_id})
        raise service_unavailable("No fue posible resolver technical items en este momento.")
    for reference in references:
        value = normalize_technical_identifier(reference.reference_value)
        if query_value == value:
            if field in {"serial_number", "internal_code"}:
                return 75
            return 65
        if query_value in value or value in query_value:
            if field in {"serial_number", "internal_code"}:
                return 45
            return 40
    return 0


def resolve_technical_items(
    db: Session,
    *,
    asset_id: int | None = None,
    part_number: str | None = None,
    serial_number: str | None = None,
    internal_code: str | None = None,
    item_id: str | None = None,
    model: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[dict]]:
    identifiers = _resolve_asset_identifiers(db, asset_id)
    explicit_identifiers = {
        "part_number": part_number,
        "serial_number": serial_number,
        "internal_code": internal_code,
        "item_id": item_id,
        "model": model,
    }
    identifiers.update({key: value for key, value in explicit_identifiers.items() if value})
    normalized_identifiers = {
        key: normalize_technical_identifier(value)
        for key, value in identifiers.items()
        if normalize_technical_identifier(value)
    }
    if not normalized_identifiers:
        return 0, []

    try:
        items = _technical_item_query(db).all()
    except SQLAlchemyError:
        logger.exception("Database error resolving technical items")
        raise service_unavailable("No fue posible resolver technical items en este momento.")

    matches: list[dict] = []
    for item in items:
        item_values = _technical_item_query_identifier_map(item)
        scores: list[int] = []
        matched_on: list[str] = []

        for field, query_value in normalized_identifiers.items():
            direct_score = _score_direct_identifier_match(field, query_value, item_values.get(field, ""))
            reference_score = _score_reference_identifier_match(
                db,
                item_id=item.id,
                field=field,
                query_value=query_value,
            )
            score = max(direct_score, reference_score)
            if score:
                scores.append(score)
                matched_on.append(field)

        if scores:
            confidence = min(100, max(scores) + min(10, (len(scores) - 1) * 5))
            matches.append(
                {
                    "technical_item": item,
                    "confidence": confidence,
                    "matched_on": sorted(set(matched_on)),
                }
            )

    matches.sort(
        key=lambda match: (
            match["confidence"],
            match["technical_item"].updated_at or match["technical_item"].created_at,
            match["technical_item"].id,
        ),
        reverse=True,
    )
    total = len(matches)
    return total, matches[skip : skip + limit]


def _is_expired(expires_at: datetime | None) -> bool:
    if not expires_at:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    return expires_at < now


def get_technical_item_packet(db: Session, technical_item_id: int) -> dict:
    technical_item = get_technical_item_or_404(db, technical_item_id)
    try:
        links = (
            db.query(TechnicalItemDocument)
            .options(
                joinedload(TechnicalItemDocument.document).joinedload(DocsDocument.file),
                joinedload(TechnicalItemDocument.document).joinedload(DocsDocument.item_references),
                joinedload(TechnicalItemDocument.document)
                .joinedload(DocsDocument.related_out)
                .joinedload(DocsRelatedDocument.related_document),
            )
            .filter(TechnicalItemDocument.technical_item_id == technical_item_id)
            .order_by(TechnicalItemDocument.relation_type.asc(), TechnicalItemDocument.created_at.desc())
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error loading technical packet", extra={"technical_item_id": technical_item_id})
        raise service_unavailable("No fue posible cargar el paquete técnico en este momento.")

    groups = {group_name: [] for group_name in TECHNICAL_PACKET_GROUPS.values()}
    warnings = []
    seen_warnings: set[tuple[str, int | None]] = set()

    def add_warning(
        warning_type: str,
        message: str,
        document: DocsDocument | None = None,
    ) -> None:
        key = (warning_type, document.id if document else None)
        if key in seen_warnings:
            return
        seen_warnings.add(key)
        warning = {
            "type": warning_type,
            "message": message,
        }
        if document:
            warning["document_id"] = document.id
            warning["document_code"] = document.document_code
        warnings.append(warning)

    if not links:
        add_warning("no_documents", "El technical item no tiene documentos asociados.")

    for link in links:
        document = link.document
        group_name = TECHNICAL_PACKET_GROUPS.get(link.relation_type, "related")
        groups[group_name].append(document)

        if not document.file:
            add_warning(
                "missing_file",
                f"El documento {document.document_code} no tiene archivo asociado.",
                document,
            )
        if document.status == DocsDocumentStatus.OBSOLETE:
            add_warning(
                "obsolete_document",
                f"El documento {document.document_code} está obsoleto.",
                document,
            )
        if document.status == DocsDocumentStatus.DRAFT:
            add_warning(
                "draft_document",
                f"El documento {document.document_code} está en borrador.",
                document,
            )
        if link.relation_type == TechnicalItemDocumentRelationType.CERTIFICATE and _is_expired(document.expires_at):
            add_warning(
                "expired_certificate",
                f"El certificado {document.document_code} está vencido.",
                document,
            )

    return {
        "technical_item": technical_item,
        "documents": groups,
        "warnings": warnings,
    }


def create_document(
    db: Session,
    data: DocsDocumentCreate,
    uploaded_by_user_id: int | None,
    *,
    actor_user_id: int | None = None,
) -> DocsDocument:
    _check_document_code_unique(db, data.document_code)
    payload = data.model_dump(exclude={"references"})
    document = DocsDocument(**payload, uploaded_by_user_id=uploaded_by_user_id)
    db.add(document)
    try:
        db.flush()
        for ref_data in data.references:
            db.add(_reference_from_payload(document.id, ref_data))
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Docs document create conflict", extra={"document_code": data.document_code})
        raise conflict("El código del documento o una referencia ya existe.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating docs document")
        raise service_unavailable("No fue posible registrar el documento en este momento.")
    _run_document_auto_link_trigger(db, document.id, actor_user_id=actor_user_id)
    return get_document_or_404(db, document.id)


def update_document(
    db: Session,
    document_id: int,
    data: DocsDocumentUpdate,
    *,
    actor_user_id: int | None = None,
) -> DocsDocument:
    document = get_document_or_404(db, document_id)
    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return document
    if "document_code" in patch:
        _check_document_code_unique(db, patch["document_code"], exclude_id=document_id)
    for field, value in patch.items():
        setattr(document, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Docs document update conflict", extra={"document_id": document_id})
        raise conflict("El código del documento ya existe.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error updating docs document", extra={"document_id": document_id})
        raise service_unavailable("No fue posible actualizar el documento en este momento.")
    if "document_type" in patch:
        _run_document_auto_link_trigger(db, document_id, actor_user_id=actor_user_id)
    return get_document_or_404(db, document_id)


def add_reference(
    db: Session,
    document_id: int,
    data: DocsItemReferenceCreate,
    *,
    actor_user_id: int | None = None,
) -> DocsItemReference:
    get_document_or_404(db, document_id)
    ref = _reference_from_payload(document_id, data)
    db.add(ref)
    try:
        db.commit()
        db.refresh(ref)
    except IntegrityError:
        db.rollback()
        raise conflict("La referencia ya está asociada a este documento.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error adding docs reference", extra={"document_id": document_id})
        raise service_unavailable("No fue posible asociar la referencia en este momento.")
    _run_document_auto_link_trigger(db, document_id, actor_user_id=actor_user_id)
    return ref


def add_related_document(
    db: Session,
    document_id: int,
    data: DocsRelatedDocumentCreate,
) -> DocsRelatedDocument:
    if document_id == data.related_document_id:
        raise bad_request("Un documento no puede relacionarse consigo mismo.")
    get_document_or_404(db, document_id)
    get_document_or_404(db, data.related_document_id)
    relation = DocsRelatedDocument(
        source_document_id=document_id,
        related_document_id=data.related_document_id,
        relation_type=data.relation_type,
    )
    db.add(relation)
    try:
        db.commit()
        db.refresh(relation)
    except IntegrityError:
        db.rollback()
        raise conflict("La relación ya existe para estos documentos.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error adding related docs document", extra={"document_id": document_id})
        raise service_unavailable("No fue posible asociar el documento relacionado en este momento.")
    return (
        db.query(DocsRelatedDocument)
        .options(joinedload(DocsRelatedDocument.related_document))
        .filter(DocsRelatedDocument.id == relation.id)
        .first()
    )


def _safe_filename(filename: str | None) -> str:
    safe_name = Path(filename or "document").name
    if not safe_name or safe_name in {".", ".."}:
        raise bad_request("El nombre del archivo no es válido.")
    if len(safe_name) > 255:
        raise bad_request("El nombre del archivo no puede superar 255 caracteres.")
    return safe_name


def _validate_document_file(file: UploadFile, filename: str, content: bytes) -> str:
    mime = (file.content_type or "").split(";")[0].strip().lower() or None
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise bad_request(
            f"Extensión '{ext}' no permitida. "
            f"Extensiones válidas: {', '.join(sorted(ALLOWED_DOC_EXTENSIONS))}."
        )
    if not mime:
        raise bad_request("No fue posible determinar el tipo MIME del archivo.")
    if mime != "application/octet-stream" and mime not in ALLOWED_DOC_MIME_TYPES:
        raise bad_request(f"Tipo de archivo '{mime}' no permitido para SGOI Docs.")
    if len(content) == 0:
        raise bad_request("El archivo está vacío.")
    if len(content) > MAX_DOC_FILE_SIZE_BYTES:
        raise bad_request(f"El archivo supera el tamaño máximo permitido de {MAX_DOC_FILE_SIZE_MB} MB.")
    return mime


def _store_document_file(content: bytes, filename: str, document_id: int, mime_type: str | None) -> dict:
    if cloudinary_service._is_configured():
        try:
            return cloudinary_service.upload_document_to_cloudinary(
                content=content,
                original_filename=filename,
                document_id=document_id,
                mime_type=mime_type,
            )
        except RuntimeError as exc:
            logger.warning(
                "Docs Cloudinary storage rejected",
                extra={"document_id": document_id, "filename": filename, "reason": str(exc)},
            )
            raise service_unavailable("No fue posible almacenar el documento en este momento.")

    ext = Path(filename).suffix
    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = _docs_upload_dir(document_id)
    relative_path = Path("docs") / str(document_id) / stored_name
    (upload_dir / stored_name).write_bytes(content)
    return {
        "storage_provider": "local",
        "file_url": str(relative_path),
        "public_id": None,
    }


async def upload_document_file(db: Session, document_id: int, file: UploadFile) -> DocsDocument:
    document = get_document_or_404(db, document_id)
    filename = _safe_filename(file.filename)
    content = await file.read()
    mime_type = _validate_document_file(file, filename, content)
    checksum = hashlib.sha256(content).hexdigest()
    stored = _store_document_file(content, filename, document_id, mime_type)

    if document.file:
        document.file.storage_provider = stored["storage_provider"]
        document.file.file_url = stored["file_url"]
        document.file.public_id = stored.get("public_id")
        document.file.filename = filename
        document.file.mime_type = mime_type
        document.file.file_size = len(content)
        document.file.checksum = checksum
    else:
        db.add(
            DocsFile(
                document_id=document_id,
                storage_provider=stored["storage_provider"],
                file_url=stored["file_url"],
                public_id=stored.get("public_id"),
                filename=filename,
                mime_type=mime_type,
                file_size=len(content),
                checksum=checksum,
            )
        )

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error uploading docs file", extra={"document_id": document_id})
        raise service_unavailable("No fue posible registrar el archivo del documento en este momento.")
    return get_document_or_404(db, document_id)


def get_document_file_or_404(db: Session, document_id: int, is_admin: bool) -> DocsFile:
    document = get_document_or_404(db, document_id)
    ensure_document_visible(document, is_admin)
    if not document.file:
        raise not_found("DocsFile", document_id)
    return document.file


def search_documents(
    db: Session,
    *,
    query: str | None = None,
    reference_type: DocsReferenceType | None = None,
    reference_value: str | None = None,
    status: DocsDocumentStatus | None = None,
    document_type: str | None = None,
    manufacturer: str | None = None,
    skip: int = 0,
    limit: int = 50,
    active_only: bool = True,
) -> tuple[int, list[DocsDocument]]:
    q = db.query(DocsDocument)
    joined_references = False

    if active_only:
        q = q.filter(DocsDocument.status == DocsDocumentStatus.ACTIVE)
    elif status:
        q = q.filter(DocsDocument.status == status)

    if document_type:
        q = q.filter(DocsDocument.document_type.ilike(f"%{document_type}%"))
    if manufacturer:
        q = q.filter(DocsDocument.manufacturer.ilike(f"%{manufacturer}%"))

    if reference_type or reference_value:
        q = q.join(DocsItemReference)
        joined_references = True
        if reference_type:
            q = q.filter(DocsItemReference.reference_type == reference_type)
        if reference_value:
            normalized = normalize_reference_value(reference_value)
            if not normalized:
                raise bad_request("reference_value debe contener al menos un carácter alfanumérico.")
            q = q.filter(DocsItemReference.normalized_value == normalized)

    search_rank = None
    if query and normalize_search_text(query):
        text_query = normalize_search_text(query)
        compact_query = compact_search_value(query)
        reference_query = normalize_reference_value(query)

        if not joined_references:
            q = q.outerjoin(DocsItemReference)
            joined_references = True

        searchable_reference = DocsItemReference.reference_type.in_(SEARCHABLE_REFERENCE_TYPES)
        exact_reference_match = (
            and_(
                searchable_reference,
                DocsItemReference.normalized_value == reference_query,
            )
            if reference_query
            else False
        )
        partial_reference_match = (
            and_(
                searchable_reference,
                DocsItemReference.normalized_value.ilike(f"%{reference_query}%"),
            )
            if reference_query
            else False
        )
        exact_document_code_match = (
            _compact_column(DocsDocument.document_code) == compact_query
            if compact_query
            else False
        )
        compact_metadata_match = (
            or_(
                _compact_column(DocsDocument.document_code).contains(compact_query),
                _compact_column(DocsDocument.manufacturer).contains(compact_query),
                _compact_column(DocsDocument.source_system).contains(compact_query),
                _compact_column(DocsDocument.revision).contains(compact_query),
            )
            if compact_query
            else False
        )
        metadata_match = or_(
            func.lower(func.coalesce(DocsDocument.document_code, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.title, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.description, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.manufacturer, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.source_system, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.revision, "")).contains(text_query),
            func.lower(func.coalesce(DocsDocument.document_type, "")).contains(text_query),
            compact_metadata_match,
        )

        q = q.filter(
            or_(
                exact_reference_match,
                exact_document_code_match,
                partial_reference_match,
                metadata_match,
            )
        )
        search_rank = func.min(
            case(
                (exact_reference_match, 0),
                (exact_document_code_match, 1),
                (partial_reference_match, 2),
                (metadata_match, 3),
                else_=9,
            )
        ).label("search_rank")
        q = q.add_columns(search_rank).group_by(DocsDocument.id)

    try:
        total = q.count()
        if search_rank is not None:
            rows = (
                q.order_by(search_rank.asc(), DocsDocument.updated_at.desc(), DocsDocument.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
            items = [row[0] for row in rows]
        else:
            items = (
                q.distinct()
                .order_by(DocsDocument.updated_at.desc(), DocsDocument.id.desc())
                .offset(skip)
                .limit(limit)
                .all()
            )
    except SQLAlchemyError:
        logger.exception("Database error searching docs documents")
        raise service_unavailable("No fue posible buscar documentos en este momento.")
    return total, items


def list_related_documents(
    db: Session,
    *,
    document_id: int,
    active_only: bool = True,
) -> list[DocsRelatedDocument]:
    get_document_or_404(db, document_id)
    q = (
        db.query(DocsRelatedDocument)
        .join(DocsRelatedDocument.related_document)
        .options(joinedload(DocsRelatedDocument.related_document))
        .filter(DocsRelatedDocument.source_document_id == document_id)
    )
    if active_only:
        q = q.filter(DocsDocument.status == DocsDocumentStatus.ACTIVE)
    try:
        return q.order_by(DocsRelatedDocument.id.asc()).all()
    except SQLAlchemyError:
        logger.exception("Database error listing related docs documents", extra={"document_id": document_id})
        raise service_unavailable("No fue posible listar documentos relacionados en este momento.")


def find_by_reference(
    db: Session,
    *,
    reference_type: DocsReferenceType,
    reference_value: str,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> tuple[str, int, list[DocsDocument]]:
    normalized = normalize_reference_value(reference_value)
    if not normalized:
        raise bad_request("reference_value debe contener al menos un carácter alfanumérico.")
    total, items = search_documents(
        db,
        reference_type=reference_type,
        reference_value=reference_value,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )
    return normalized, total, items


def get_technical_item_or_404(db: Session, technical_item_id: int) -> TechnicalItem:
    try:
        item = _technical_item_query(db).filter(TechnicalItem.id == technical_item_id).first()
    except SQLAlchemyError:
        logger.exception(
            "Database error loading technical item",
            extra={"technical_item_id": technical_item_id},
        )
        raise service_unavailable("No fue posible consultar el technical item en este momento.")
    if not item:
        raise not_found("TechnicalItem", technical_item_id)
    return item


def list_technical_items(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    status: str | None = None,
    manufacturer: str | None = None,
    category: str | None = None,
) -> tuple[int, list[TechnicalItem]]:
    q = _technical_item_query(db)

    if status:
        q = q.filter(TechnicalItem.status == status)
    if manufacturer:
        q = q.filter(TechnicalItem.manufacturer.ilike(f"%{manufacturer}%"))
    if category:
        q = q.filter(TechnicalItem.category.ilike(f"%{category}%"))
    if search and search.strip():
        value = search.strip()
        like = f"%{value}%"
        q = q.filter(
            or_(
                TechnicalItem.item_id.ilike(like),
                TechnicalItem.part_number.ilike(like),
                TechnicalItem.name.ilike(like),
                TechnicalItem.model.ilike(like),
                TechnicalItem.manufacturer.ilike(like),
                TechnicalItem.manufacturer_code.ilike(like),
                TechnicalItem.category.ilike(like),
                TechnicalItem.equipment_family.ilike(like),
                TechnicalItem.description.ilike(like),
                TechnicalItem.source_system.ilike(like),
            )
        )

    try:
        total = q.count()
        items = (
            q.order_by(TechnicalItem.updated_at.desc(), TechnicalItem.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error listing technical items", extra={"skip": skip, "limit": limit})
        raise service_unavailable("No fue posible listar technical items en este momento.")
    return total, items


def create_technical_item(
    db: Session,
    data: TechnicalItemCreate,
    *,
    actor_user_id: int | None = None,
) -> TechnicalItem:
    _check_technical_item_id_unique(db, data.item_id)
    item = TechnicalItem(**data.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Technical item create conflict", extra={"item_id": data.item_id})
        raise conflict("El item_id del technical item ya existe.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error creating technical item")
        raise service_unavailable("No fue posible crear el technical item en este momento.")
    _run_technical_item_auto_link_trigger(db, item.id, actor_user_id=actor_user_id)
    return get_technical_item_or_404(db, item.id)


def update_technical_item(
    db: Session,
    technical_item_id: int,
    data: TechnicalItemUpdate,
    *,
    actor_user_id: int | None = None,
) -> TechnicalItem:
    item = get_technical_item_or_404(db, technical_item_id)
    patch = data.model_dump(exclude_unset=True)
    if not patch:
        return item
    if "item_id" in patch:
        _check_technical_item_id_unique(db, patch["item_id"], exclude_id=technical_item_id)
    for field, value in patch.items():
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Technical item update conflict", extra={"technical_item_id": technical_item_id})
        raise conflict("El item_id del technical item ya existe.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error updating technical item",
            extra={"technical_item_id": technical_item_id},
        )
        raise service_unavailable("No fue posible actualizar el technical item en este momento.")
    if {"item_id", "part_number", "model", "manufacturer_code"} & set(patch):
        _run_technical_item_auto_link_trigger(db, technical_item_id, actor_user_id=actor_user_id)
    return get_technical_item_or_404(db, technical_item_id)


def attach_document_to_technical_item(
    db: Session,
    technical_item_id: int,
    data: TechnicalItemDocumentAttach,
) -> TechnicalItemDocument:
    get_technical_item_or_404(db, technical_item_id)
    get_document_or_404(db, data.document_id)
    link = TechnicalItemDocument(
        technical_item_id=technical_item_id,
        document_id=data.document_id,
        relation_type=data.relation_type,
    )
    db.add(link)
    try:
        db.commit()
        db.refresh(link)
    except IntegrityError:
        db.rollback()
        raise conflict("El documento ya está asociado a este technical item.")
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error attaching docs document to technical item",
            extra={"technical_item_id": technical_item_id, "document_id": data.document_id},
        )
        raise service_unavailable("No fue posible asociar el documento al technical item en este momento.")
    return (
        db.query(TechnicalItemDocument)
        .options(joinedload(TechnicalItemDocument.document))
        .filter(TechnicalItemDocument.id == link.id)
        .first()
    )


def detach_document_from_technical_item(db: Session, technical_item_id: int, document_id: int) -> None:
    get_technical_item_or_404(db, technical_item_id)
    links = (
        db.query(TechnicalItemDocument)
        .filter(
            TechnicalItemDocument.technical_item_id == technical_item_id,
            TechnicalItemDocument.document_id == document_id,
        )
        .all()
    )
    if not links:
        raise not_found("TechnicalItemDocument", document_id)
    try:
        for link in links:
            db.delete(link)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Database error detaching docs document from technical item",
            extra={"technical_item_id": technical_item_id, "document_id": document_id},
        )
        raise service_unavailable("No fue posible desvincular el documento del technical item en este momento.")
