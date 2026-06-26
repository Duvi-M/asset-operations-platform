from datetime import date, datetime

from pydantic import Field, model_validator

from app.models.docs import (
    DocsDocumentStatus,
    DocsReferenceType,
    DocsRelationType,
    TechnicalItemDocumentRelationType,
)
from app.schemas.base import AppModel


class DocsFileRead(AppModel):
    id: int
    document_id: int
    storage_provider: str
    file_url: str
    public_id: str | None
    filename: str
    mime_type: str | None
    file_size: int | None
    checksum: str | None
    created_at: datetime


class DocsItemReferenceCreate(AppModel):
    reference_type: DocsReferenceType
    reference_value: str = Field(..., min_length=1, max_length=255)
    label: str | None = Field(None, max_length=255)


class DocsItemReferenceRead(AppModel):
    id: int
    document_id: int
    reference_type: DocsReferenceType
    reference_value: str
    normalized_value: str
    label: str | None


class DocsDocumentBase(AppModel):
    document_code: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)
    document_type: str = Field(..., min_length=1, max_length=100)
    status: DocsDocumentStatus = DocsDocumentStatus.DRAFT
    revision: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=20)
    manufacturer: str | None = Field(None, max_length=255)
    source_system: str | None = Field("sgoi_docs", max_length=100)
    effective_date: date | None = None
    expires_at: datetime | None = None


class DocsDocumentCreate(DocsDocumentBase):
    references: list[DocsItemReferenceCreate] = Field(default_factory=list)


class DocsDocumentUpdate(AppModel):
    document_code: str | None = Field(None, min_length=1, max_length=100)
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10000)
    document_type: str | None = Field(None, min_length=1, max_length=100)
    status: DocsDocumentStatus | None = None
    revision: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=20)
    manufacturer: str | None = Field(None, max_length=255)
    source_system: str | None = Field(None, max_length=100)
    effective_date: date | None = None
    expires_at: datetime | None = None


class DocsDocumentReadSlim(AppModel):
    id: int
    document_code: str
    title: str
    document_type: str
    status: DocsDocumentStatus
    revision: str | None
    language: str | None
    manufacturer: str | None


class DocsRelatedDocumentCreate(AppModel):
    related_document_id: int = Field(..., gt=0)
    relation_type: DocsRelationType


class DocsRelatedDocumentRead(AppModel):
    id: int
    source_document_id: int
    related_document_id: int
    relation_type: DocsRelationType
    related_document: DocsDocumentReadSlim


class DocsDocumentRead(DocsDocumentReadSlim):
    description: str | None
    source_system: str | None
    effective_date: date | None
    expires_at: datetime | None
    uploaded_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    file: DocsFileRead | None = None
    item_references: list[DocsItemReferenceRead] = Field(default_factory=list)
    related_out: list[DocsRelatedDocumentRead] = Field(default_factory=list)


class DocsSearchResponse(AppModel):
    total: int
    items: list[DocsDocumentReadSlim]


class DocsReferenceLookupResponse(AppModel):
    reference_type: DocsReferenceType
    reference_value: str
    normalized_value: str
    total: int
    items: list[DocsDocumentReadSlim]


class DocsFileUploadResponse(AppModel):
    document: DocsDocumentRead
    file: DocsFileRead

    @model_validator(mode="after")
    def require_file(self) -> "DocsFileUploadResponse":
        if self.file.document_id != self.document.id:
            raise ValueError("La metadata del archivo no corresponde al documento.")
        return self


class TechnicalItemBase(AppModel):
    item_id: str = Field(..., min_length=1, max_length=100)
    part_number: str | None = Field(None, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    model: str | None = Field(None, max_length=100)
    manufacturer: str | None = Field(None, max_length=255)
    manufacturer_code: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    equipment_family: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=10000)
    source_system: str | None = Field("sgoi_docs", max_length=100)
    status: str = Field("active", min_length=1, max_length=50)


class TechnicalItemCreate(TechnicalItemBase):
    pass


class TechnicalItemUpdate(AppModel):
    item_id: str | None = Field(None, min_length=1, max_length=100)
    part_number: str | None = Field(None, max_length=100)
    name: str | None = Field(None, min_length=1, max_length=255)
    model: str | None = Field(None, max_length=100)
    manufacturer: str | None = Field(None, max_length=255)
    manufacturer_code: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=100)
    equipment_family: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=10000)
    source_system: str | None = Field(None, max_length=100)
    status: str | None = Field(None, min_length=1, max_length=50)


class TechnicalItemDocumentAttach(AppModel):
    document_id: int = Field(..., gt=0)
    relation_type: TechnicalItemDocumentRelationType = TechnicalItemDocumentRelationType.RELATED


class TechnicalItemDocumentRead(AppModel):
    id: int
    technical_item_id: int
    document_id: int
    relation_type: TechnicalItemDocumentRelationType
    created_at: datetime
    document: DocsDocumentReadSlim


class TechnicalItemRead(TechnicalItemBase):
    id: int
    created_at: datetime
    updated_at: datetime
    documents: list[TechnicalItemDocumentRead] = Field(default_factory=list)


class TechnicalItemSearchResponse(AppModel):
    total: int
    items: list[TechnicalItemRead]


class TechnicalItemResolveMatch(AppModel):
    technical_item: TechnicalItemRead
    confidence: int
    matched_on: list[str] = Field(default_factory=list)


class TechnicalItemResolveResponse(AppModel):
    total: int
    items: list[TechnicalItemResolveMatch]


class TechnicalPacketDocumentGroups(AppModel):
    manuals: list[DocsDocumentRead] = Field(default_factory=list)
    certificates: list[DocsDocumentRead] = Field(default_factory=list)
    diagrams: list[DocsDocumentRead] = Field(default_factory=list)
    procedures: list[DocsDocumentRead] = Field(default_factory=list)
    datasheets: list[DocsDocumentRead] = Field(default_factory=list)
    reports: list[DocsDocumentRead] = Field(default_factory=list)
    related: list[DocsDocumentRead] = Field(default_factory=list)


class TechnicalPacketWarning(AppModel):
    type: str
    message: str
    document_id: int | None = None
    document_code: str | None = None


class TechnicalItemPacketResponse(AppModel):
    technical_item: TechnicalItemRead
    documents: TechnicalPacketDocumentGroups
    warnings: list[TechnicalPacketWarning] = Field(default_factory=list)
