import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocsDocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    OBSOLETE = "obsolete"


class DocsReferenceType(str, enum.Enum):
    PART_NUMBER = "part_number"
    ITEM_ID = "item_id"
    SERIAL_NUMBER = "serial_number"
    INTERNAL_CODE = "internal_code"
    ASSET_ID = "asset_id"
    PART_ID = "part_id"
    MODEL = "model"
    MANUFACTURER_CODE = "manufacturer_code"


class DocsRelationType(str, enum.Enum):
    SUPERSEDES = "supersedes"
    REPLACES = "replaces"
    REFERENCES = "references"
    SAME_EQUIPMENT = "same_equipment"
    CERTIFICATE_FOR = "certificate_for"
    PROCEDURE_FOR = "procedure_for"


class TechnicalItemDocumentRelationType(str, enum.Enum):
    MANUAL = "manual"
    CERTIFICATE = "certificate"
    DIAGRAM = "diagram"
    PROCEDURE = "procedure"
    DATASHEET = "datasheet"
    REPORT = "report"
    RELATED = "related"


class DocsDocument(Base):
    """Technical document metadata owned by the SGOI Docs bounded module."""

    __tablename__ = "docs_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[DocsDocumentStatus] = mapped_column(
        Enum(
            DocsDocumentStatus,
            name="docs_document_status",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=DocsDocumentStatus.DRAFT,
        index=True,
    )
    revision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    uploaded_by = relationship("User", passive_deletes=True)
    file: Mapped["DocsFile | None"] = relationship(
        "DocsFile",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
    )
    item_references: Mapped[list["DocsItemReference"]] = relationship(
        "DocsItemReference",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    related_out: Mapped[list["DocsRelatedDocument"]] = relationship(
        "DocsRelatedDocument",
        foreign_keys="DocsRelatedDocument.source_document_id",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )
    related_in: Mapped[list["DocsRelatedDocument"]] = relationship(
        "DocsRelatedDocument",
        foreign_keys="DocsRelatedDocument.related_document_id",
        back_populates="related_document",
        cascade="all, delete-orphan",
    )
    technical_item_links: Mapped[list["TechnicalItemDocument"]] = relationship(
        "TechnicalItemDocument",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocsDocument id={self.id} code={self.document_code!r} status={self.status}>"


class DocsFile(Base):
    """Stored file metadata for a Docs document. MVP uses one file per document."""

    __tablename__ = "docs_files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("docs_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    public_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[DocsDocument] = relationship("DocsDocument", back_populates="file")

    def __repr__(self) -> str:
        return f"<DocsFile id={self.id} document_id={self.document_id} filename={self.filename!r}>"


class DocsItemReference(Base):
    """Searchable reference connecting a document to equipment, parts, or codes."""

    __tablename__ = "docs_item_references"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "reference_type",
            "normalized_value",
            name="uq_docs_item_reference_document_type_value",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("docs_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference_type: Mapped[DocsReferenceType] = mapped_column(
        Enum(
            DocsReferenceType,
            name="docs_reference_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    reference_value: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped[DocsDocument] = relationship("DocsDocument", back_populates="item_references")

    def __repr__(self) -> str:
        return f"<DocsItemReference document_id={self.document_id} type={self.reference_type} value={self.reference_value!r}>"


class DocsRelatedDocument(Base):
    """Typed relationship between two Docs documents."""

    __tablename__ = "docs_related_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "related_document_id",
            "relation_type",
            name="uq_docs_related_document_pair_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("docs_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    related_document_id: Mapped[int] = mapped_column(
        ForeignKey("docs_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[DocsRelationType] = mapped_column(
        Enum(
            DocsRelationType,
            name="docs_relation_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    source_document: Mapped[DocsDocument] = relationship(
        "DocsDocument",
        foreign_keys=[source_document_id],
        back_populates="related_out",
    )
    related_document: Mapped[DocsDocument] = relationship(
        "DocsDocument",
        foreign_keys=[related_document_id],
        back_populates="related_in",
    )

    def __repr__(self) -> str:
        return (
            f"<DocsRelatedDocument source={self.source_document_id} "
            f"related={self.related_document_id} type={self.relation_type}>"
        )


class TechnicalItem(Base):
    """Catalog item foundation for SGOI Docs technical documentation lookup."""

    __tablename__ = "docs_technical_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    part_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    manufacturer_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    equipment_family: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    documents: Mapped[list["TechnicalItemDocument"]] = relationship(
        "TechnicalItemDocument",
        back_populates="technical_item",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TechnicalItem id={self.id} item_id={self.item_id!r} status={self.status!r}>"


class TechnicalItemDocument(Base):
    """Typed link between a technical catalog item and a Docs document."""

    __tablename__ = "docs_technical_item_documents"
    __table_args__ = (
        UniqueConstraint(
            "technical_item_id",
            "document_id",
            "relation_type",
            name="uq_docs_technical_item_document_relation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    technical_item_id: Mapped[int] = mapped_column(
        ForeignKey("docs_technical_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("docs_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[TechnicalItemDocumentRelationType] = mapped_column(
        Enum(
            TechnicalItemDocumentRelationType,
            name="technical_item_document_relation_type",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=TechnicalItemDocumentRelationType.RELATED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    technical_item: Mapped[TechnicalItem] = relationship(
        "TechnicalItem",
        back_populates="documents",
    )
    document: Mapped[DocsDocument] = relationship(
        "DocsDocument",
        back_populates="technical_item_links",
    )

    def __repr__(self) -> str:
        return (
            f"<TechnicalItemDocument technical_item_id={self.technical_item_id} "
            f"document_id={self.document_id} relation_type={self.relation_type}>"
        )
