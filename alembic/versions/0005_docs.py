"""add sgoi docs module

Revision ID: 0005_docs
Revises: 0004_audit_logs
Create Date: 2026-06-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_docs"
down_revision: Union[str, None] = "0004_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


docs_document_status = postgresql.ENUM(
    "draft",
    "active",
    "obsolete",
    name="docs_document_status",
    create_type=False,
)
docs_reference_type = postgresql.ENUM(
    "part_number",
    "item_id",
    "serial_number",
    "internal_code",
    "asset_id",
    "part_id",
    "model",
    "manufacturer_code",
    name="docs_reference_type",
    create_type=False,
)
docs_relation_type = postgresql.ENUM(
    "supersedes",
    "replaces",
    "references",
    "same_equipment",
    "certificate_for",
    "procedure_for",
    name="docs_relation_type",
    create_type=False,
)


def _create_enums() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE docs_document_status AS ENUM ('draft', 'active', 'obsolete');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE docs_reference_type AS ENUM (
                'part_number',
                'item_id',
                'serial_number',
                'internal_code',
                'asset_id',
                'part_id',
                'model',
                'manufacturer_code'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE docs_relation_type AS ENUM (
                'supersedes',
                'replaces',
                'references',
                'same_equipment',
                'certificate_for',
                'procedure_for'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "docs_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("status", docs_document_status, nullable=False, server_default="draft"),
        sa.Column("revision", sa.String(length=50), nullable=True),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("source_system", sa.String(length=100), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_code"),
    )
    op.create_index(op.f("ix_docs_documents_document_type"), "docs_documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_docs_documents_id"), "docs_documents", ["id"], unique=False)
    op.create_index(op.f("ix_docs_documents_manufacturer"), "docs_documents", ["manufacturer"], unique=False)
    op.create_index(op.f("ix_docs_documents_status"), "docs_documents", ["status"], unique=False)
    op.create_index(op.f("ix_docs_documents_title"), "docs_documents", ["title"], unique=False)
    op.create_index(op.f("ix_docs_documents_uploaded_by_user_id"), "docs_documents", ["uploaded_by_user_id"], unique=False)

    op.create_table(
        "docs_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("file_url", sa.String(length=1000), nullable=False),
        sa.Column("public_id", sa.String(length=500), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["docs_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(op.f("ix_docs_files_id"), "docs_files", ["id"], unique=False)

    op.create_table(
        "docs_item_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("reference_type", docs_reference_type, nullable=False),
        sa.Column("reference_value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["docs_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "reference_type",
            "normalized_value",
            name="uq_docs_item_reference_document_type_value",
        ),
    )
    op.create_index(op.f("ix_docs_item_references_document_id"), "docs_item_references", ["document_id"], unique=False)
    op.create_index(op.f("ix_docs_item_references_id"), "docs_item_references", ["id"], unique=False)
    op.create_index(op.f("ix_docs_item_references_normalized_value"), "docs_item_references", ["normalized_value"], unique=False)
    op.create_index(op.f("ix_docs_item_references_reference_type"), "docs_item_references", ["reference_type"], unique=False)

    op.create_table(
        "docs_related_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("related_document_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", docs_relation_type, nullable=False),
        sa.ForeignKeyConstraint(["related_document_id"], ["docs_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["docs_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_document_id",
            "related_document_id",
            "relation_type",
            name="uq_docs_related_document_pair_type",
        ),
    )
    op.create_index(op.f("ix_docs_related_documents_id"), "docs_related_documents", ["id"], unique=False)
    op.create_index(op.f("ix_docs_related_documents_related_document_id"), "docs_related_documents", ["related_document_id"], unique=False)
    op.create_index(op.f("ix_docs_related_documents_relation_type"), "docs_related_documents", ["relation_type"], unique=False)
    op.create_index(op.f("ix_docs_related_documents_source_document_id"), "docs_related_documents", ["source_document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_docs_related_documents_source_document_id"), table_name="docs_related_documents")
    op.drop_index(op.f("ix_docs_related_documents_relation_type"), table_name="docs_related_documents")
    op.drop_index(op.f("ix_docs_related_documents_related_document_id"), table_name="docs_related_documents")
    op.drop_index(op.f("ix_docs_related_documents_id"), table_name="docs_related_documents")
    op.drop_table("docs_related_documents")

    op.drop_index(op.f("ix_docs_item_references_reference_type"), table_name="docs_item_references")
    op.drop_index(op.f("ix_docs_item_references_normalized_value"), table_name="docs_item_references")
    op.drop_index(op.f("ix_docs_item_references_id"), table_name="docs_item_references")
    op.drop_index(op.f("ix_docs_item_references_document_id"), table_name="docs_item_references")
    op.drop_table("docs_item_references")

    op.drop_index(op.f("ix_docs_files_id"), table_name="docs_files")
    op.drop_table("docs_files")

    op.drop_index(op.f("ix_docs_documents_uploaded_by_user_id"), table_name="docs_documents")
    op.drop_index(op.f("ix_docs_documents_title"), table_name="docs_documents")
    op.drop_index(op.f("ix_docs_documents_status"), table_name="docs_documents")
    op.drop_index(op.f("ix_docs_documents_manufacturer"), table_name="docs_documents")
    op.drop_index(op.f("ix_docs_documents_id"), table_name="docs_documents")
    op.drop_index(op.f("ix_docs_documents_document_type"), table_name="docs_documents")
    op.drop_table("docs_documents")

    op.execute("DROP TYPE IF EXISTS docs_relation_type")
    op.execute("DROP TYPE IF EXISTS docs_reference_type")
    op.execute("DROP TYPE IF EXISTS docs_document_status")
