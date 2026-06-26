from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.docs import DocsDocumentStatus, DocsReferenceType
from app.models.user import User, UserRole
from app.schemas.docs import (
    DocsDocumentCreate,
    DocsDocumentRead,
    DocsDocumentUpdate,
    DocsFileRead,
    DocsFileUploadResponse,
    DocsItemReferenceCreate,
    DocsItemReferenceRead,
    DocsReferenceLookupResponse,
    DocsRelatedDocumentCreate,
    DocsRelatedDocumentRead,
    DocsSearchResponse,
    TechnicalItemCreate,
    TechnicalItemDocumentAttach,
    TechnicalItemDocumentRead,
    TechnicalItemPacketResponse,
    TechnicalItemRead,
    TechnicalItemResolveResponse,
    TechnicalItemSearchResponse,
    TechnicalItemUpdate,
)
from app.services import audit_service, cloudinary_service, docs_service
from app.services.exceptions import not_found

router = APIRouter(prefix="/docs", tags=["SGOI Docs"], dependencies=[Depends(get_current_user)])


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


@router.get(
    "/search",
    response_model=DocsSearchResponse,
    summary="Buscar documentos técnicos en SGOI Docs",
)
def search_documents(
    query: str | None = Query(None, description="Busca en código, título, descripción, tipo y fabricante"),
    reference_type: DocsReferenceType | None = Query(None),
    reference_value: str | None = Query(None),
    status: DocsDocumentStatus | None = Query(None),
    document_type: str | None = Query(None),
    manufacturer: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = docs_service.search_documents(
        db,
        query=query,
        reference_type=reference_type,
        reference_value=reference_value,
        status=status,
        document_type=document_type,
        manufacturer=manufacturer,
        skip=skip,
        limit=limit,
        active_only=not _is_admin(current_user),
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_searched",
        entity_type="docs_document",
        metadata={
            "query": query,
            "reference_type": reference_type.value if reference_type else None,
            "reference_value": reference_value,
            "status": status.value if status else None,
            "document_type": document_type,
            "manufacturer": manufacturer,
            "total": total,
        },
    )
    return DocsSearchResponse(total=total, items=items)


@router.get(
    "/items",
    response_model=TechnicalItemSearchResponse,
    summary="Listar technical items del catálogo documental",
)
def list_technical_items(
    search: str | None = Query(None),
    status: str | None = Query(None),
    manufacturer: str | None = Query(None),
    category: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = docs_service.list_technical_items(
        db,
        search=search,
        status=status,
        manufacturer=manufacturer,
        category=category,
        skip=skip,
        limit=limit,
    )
    return TechnicalItemSearchResponse(total=total, items=items)


@router.get(
    "/items/resolve",
    response_model=TechnicalItemResolveResponse,
    summary="Resolver technical items por identificadores de Core o catálogo",
)
def resolve_technical_items(
    asset_id: int | None = Query(None, gt=0),
    part_number: str | None = Query(None),
    serial_number: str | None = Query(None),
    internal_code: str | None = Query(None),
    item_id: str | None = Query(None),
    model: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = docs_service.resolve_technical_items(
        db,
        asset_id=asset_id,
        part_number=part_number,
        serial_number=serial_number,
        internal_code=internal_code,
        item_id=item_id,
        model=model,
        skip=skip,
        limit=limit,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="resolve_technical_item",
        entity_type="technical_item",
        metadata={
            "asset_id": asset_id,
            "part_number": part_number,
            "serial_number": serial_number,
            "internal_code": internal_code,
            "item_id": item_id,
            "model": model,
            "total": total,
        },
    )
    return TechnicalItemResolveResponse(total=total, items=items)


@router.post(
    "/items",
    response_model=TechnicalItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un technical item",
)
def create_technical_item(
    data: TechnicalItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = docs_service.create_technical_item(db, data, actor_user_id=current_user.id)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_technical_item_created",
        entity_type="technical_item",
        entity_id=item.id,
        metadata={"item_id": item.item_id, "name": item.name, "status": item.status},
    )
    return item


@router.get(
    "/items/{technical_item_id}",
    response_model=TechnicalItemRead,
    summary="Obtener un technical item",
)
def get_technical_item(
    technical_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return docs_service.get_technical_item_or_404(db, technical_item_id)


@router.get(
    "/items/{technical_item_id}/packet",
    response_model=TechnicalItemPacketResponse,
    summary="Obtener paquete técnico agrupado de un technical item",
)
def get_technical_item_packet(
    technical_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    packet = docs_service.get_technical_item_packet(db, technical_item_id)
    audit_service.log_action(
        user_id=current_user.id,
        action="view_technical_packet",
        entity_type="technical_item",
        entity_id=technical_item_id,
        metadata={
            "warnings": [warning["type"] for warning in packet["warnings"]],
        },
    )
    return packet


@router.patch(
    "/items/{technical_item_id}",
    response_model=TechnicalItemRead,
    summary="Actualizar un technical item",
)
def update_technical_item(
    technical_item_id: int,
    data: TechnicalItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    item = docs_service.update_technical_item(db, technical_item_id, data, actor_user_id=current_user.id)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_technical_item_updated",
        entity_type="technical_item",
        entity_id=item.id,
        metadata={"updated_fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return item


@router.post(
    "/items/{technical_item_id}/documents",
    response_model=TechnicalItemDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Asociar un documento a un technical item",
)
def attach_document_to_technical_item(
    technical_item_id: int,
    data: TechnicalItemDocumentAttach,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    link = docs_service.attach_document_to_technical_item(db, technical_item_id, data)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_technical_item_document_attached",
        entity_type="technical_item",
        entity_id=technical_item_id,
        metadata={"document_id": data.document_id, "relation_type": data.relation_type.value},
    )
    return link


@router.delete(
    "/items/{technical_item_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desvincular un documento de un technical item",
)
def detach_document_from_technical_item(
    technical_item_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    docs_service.detach_document_from_technical_item(db, technical_item_id, document_id)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_technical_item_document_detached",
        entity_type="technical_item",
        entity_id=technical_item_id,
        metadata={"document_id": document_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/documents",
    response_model=DocsDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear metadata de un documento técnico",
)
def create_document(
    data: DocsDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = docs_service.create_document(
        db,
        data,
        uploaded_by_user_id=current_user.id,
        actor_user_id=current_user.id,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_uploaded",
        entity_type="docs_document",
        entity_id=document.id,
        metadata={
            "document_code": document.document_code,
            "title": document.title,
            "status": document.status.value,
            "has_file": bool(document.file),
        },
    )
    return document


@router.get(
    "/documents",
    response_model=DocsSearchResponse,
    summary="Listar documentos técnicos",
)
def list_documents(
    status: DocsDocumentStatus | None = Query(None),
    document_type: str | None = Query(None),
    manufacturer: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total, items = docs_service.search_documents(
        db,
        status=status,
        document_type=document_type,
        manufacturer=manufacturer,
        skip=skip,
        limit=limit,
        active_only=not _is_admin(current_user),
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_searched",
        entity_type="docs_document",
        metadata={
            "status": status.value if status else None,
            "document_type": document_type,
            "manufacturer": manufacturer,
            "total": total,
        },
    )
    return DocsSearchResponse(total=total, items=items)


@router.get(
    "/documents/{document_id}",
    response_model=DocsDocumentRead,
    summary="Obtener un documento técnico",
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = docs_service.get_document_or_404(db, document_id)
    is_admin = _is_admin(current_user)
    docs_service.ensure_document_visible(document, is_admin)
    response = DocsDocumentRead.model_validate(document)
    if not is_admin:
        response.related_out = [
            relation
            for relation in response.related_out
            if relation.related_document.status == DocsDocumentStatus.ACTIVE
        ]
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_viewed",
        entity_type="docs_document",
        entity_id=document.id,
        metadata={"document_code": document.document_code},
    )
    return response


@router.patch(
    "/documents/{document_id}",
    response_model=DocsDocumentRead,
    summary="Actualizar metadata o estado de un documento técnico",
)
def update_document(
    document_id: int,
    data: DocsDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = docs_service.update_document(db, document_id, data, actor_user_id=current_user.id)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_updated",
        entity_type="docs_document",
        entity_id=document.id,
        metadata={"updated_fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return document


@router.post(
    "/documents/{document_id}/file",
    response_model=DocsFileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir o reemplazar el archivo de un documento técnico",
)
async def upload_document_file(
    document_id: int,
    file: UploadFile = File(..., description="Archivo técnico a subir"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    document = await docs_service.upload_document_file(db, document_id, file)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_uploaded",
        entity_type="docs_document",
        entity_id=document.id,
        metadata={
            "document_code": document.document_code,
            "filename": document.file.filename if document.file else None,
            "mime_type": document.file.mime_type if document.file else None,
            "file_size": document.file.file_size if document.file else None,
        },
    )
    return DocsFileUploadResponse(document=document, file=document.file)


@router.get(
    "/documents/{document_id}/file",
    response_model=DocsFileRead,
    summary="Obtener metadata del archivo de un documento técnico",
)
def get_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs_file = docs_service.get_document_file_or_404(db, document_id, _is_admin(current_user))
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_viewed",
        entity_type="docs_document",
        entity_id=document_id,
        metadata={"file_id": docs_file.id, "filename": docs_file.filename},
    )
    return docs_file


@router.get(
    "/documents/{document_id}/file/open",
    summary="Abrir o descargar el archivo activo de un documento técnico",
)
def open_document_file(
    document_id: int,
    download: bool = Query(False, description="Si true, sugiere descarga como attachment"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs_file = docs_service.get_document_file_or_404(db, document_id, _is_admin(current_user))
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_downloaded" if download else "docs_document_viewed",
        entity_type="docs_document",
        entity_id=document_id,
        metadata={"file_id": docs_file.id, "filename": docs_file.filename},
    )

    if cloudinary_service.is_url(docs_file.file_url):
        return RedirectResponse(docs_file.file_url)

    path = Path(settings.media_dir) / docs_file.file_url
    if not path.exists():
        raise not_found("DocsFile", document_id)
    return FileResponse(
        path,
        media_type=docs_file.mime_type,
        filename=docs_file.filename if download else None,
    )


@router.post(
    "/documents/{document_id}/references",
    response_model=DocsItemReferenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Asociar una referencia de equipo, parte o código a un documento",
)
def add_document_reference(
    document_id: int,
    data: DocsItemReferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ref = docs_service.add_reference(db, document_id, data, actor_user_id=current_user.id)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_updated",
        entity_type="docs_document",
        entity_id=document_id,
        metadata={
            "change": "reference_added",
            "reference_type": ref.reference_type.value,
            "reference_value": ref.reference_value,
        },
    )
    return ref


@router.post(
    "/documents/{document_id}/related",
    response_model=DocsRelatedDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Relacionar otro documento técnico",
)
def add_related_document(
    document_id: int,
    data: DocsRelatedDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    relation = docs_service.add_related_document(db, document_id, data)
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_updated",
        entity_type="docs_document",
        entity_id=document_id,
        metadata={
            "change": "related_document_added",
            "related_document_id": data.related_document_id,
            "relation_type": data.relation_type.value,
        },
    )
    return relation


@router.get(
    "/documents/{document_id}/related",
    response_model=list[DocsRelatedDocumentRead],
    summary="Listar documentos técnicos relacionados",
)
def list_related_documents(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = docs_service.get_document_or_404(db, document_id)
    is_admin = _is_admin(current_user)
    docs_service.ensure_document_visible(document, is_admin)
    relations = docs_service.list_related_documents(
        db,
        document_id=document_id,
        active_only=not is_admin,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_viewed",
        entity_type="docs_document",
        entity_id=document_id,
        metadata={"view": "related_documents", "total": len(relations)},
    )
    return relations


@router.get(
    "/references/{reference_type}/{reference_value}",
    response_model=DocsReferenceLookupResponse,
    summary="Buscar documentos activos por referencia normalizada",
)
def find_documents_by_reference(
    reference_type: DocsReferenceType,
    reference_value: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized, total, items = docs_service.find_by_reference(
        db,
        reference_type=reference_type,
        reference_value=reference_value,
        active_only=not _is_admin(current_user),
        skip=skip,
        limit=limit,
    )
    audit_service.log_action(
        user_id=current_user.id,
        action="docs_document_searched",
        entity_type="docs_document",
        metadata={
            "reference_type": reference_type.value,
            "reference_value": reference_value,
            "normalized_value": normalized,
            "total": total,
        },
    )
    return DocsReferenceLookupResponse(
        reference_type=reference_type,
        reference_value=reference_value,
        normalized_value=normalized,
        total=total,
        items=items,
    )
