"""add technical catalog items

Revision ID: 0007_tech_items
Revises: 0006_work_orders
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_tech_items"
down_revision: Union[str, None] = "0006_work_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


technical_item_document_relation_type = postgresql.ENUM(
    "manual",
    "certificate",
    "diagram",
    "procedure",
    "datasheet",
    "report",
    "related",
    name="technical_item_document_relation_type",
    create_type=False,
)


def _create_enums() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE technical_item_document_relation_type AS ENUM (
                'manual',
                'certificate',
                'diagram',
                'procedure',
                'datasheet',
                'report',
                'related'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "docs_technical_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("part_number", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("manufacturer_code", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("equipment_family", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_system", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_docs_technical_items_category"), "docs_technical_items", ["category"], unique=False)
    op.create_index(
        op.f("ix_docs_technical_items_equipment_family"),
        "docs_technical_items",
        ["equipment_family"],
        unique=False,
    )
    op.create_index(op.f("ix_docs_technical_items_id"), "docs_technical_items", ["id"], unique=False)
    op.create_index(op.f("ix_docs_technical_items_item_id"), "docs_technical_items", ["item_id"], unique=True)
    op.create_index(
        op.f("ix_docs_technical_items_manufacturer"),
        "docs_technical_items",
        ["manufacturer"],
        unique=False,
    )
    op.create_index(
        op.f("ix_docs_technical_items_manufacturer_code"),
        "docs_technical_items",
        ["manufacturer_code"],
        unique=False,
    )
    op.create_index(op.f("ix_docs_technical_items_model"), "docs_technical_items", ["model"], unique=False)
    op.create_index(
        op.f("ix_docs_technical_items_part_number"),
        "docs_technical_items",
        ["part_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_docs_technical_items_source_system"),
        "docs_technical_items",
        ["source_system"],
        unique=False,
    )
    op.create_index(op.f("ix_docs_technical_items_status"), "docs_technical_items", ["status"], unique=False)
    op.create_index(op.f("ix_docs_technical_items_name"), "docs_technical_items", ["name"], unique=False)

    op.create_table(
        "docs_technical_item_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("technical_item_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("relation_type", technical_item_document_relation_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["document_id"], ["docs_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["technical_item_id"], ["docs_technical_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "technical_item_id",
            "document_id",
            "relation_type",
            name="uq_docs_technical_item_document_relation",
        ),
    )
    op.create_index(op.f("ix_docs_technical_item_documents_id"), "docs_technical_item_documents", ["id"], unique=False)
    op.create_index(
        op.f("ix_docs_technical_item_documents_document_id"),
        "docs_technical_item_documents",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_docs_technical_item_documents_relation_type"),
        "docs_technical_item_documents",
        ["relation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_docs_technical_item_documents_technical_item_id"),
        "docs_technical_item_documents",
        ["technical_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_docs_technical_item_documents_technical_item_id"),
        table_name="docs_technical_item_documents",
    )
    op.drop_index(
        op.f("ix_docs_technical_item_documents_relation_type"),
        table_name="docs_technical_item_documents",
    )
    op.drop_index(
        op.f("ix_docs_technical_item_documents_document_id"),
        table_name="docs_technical_item_documents",
    )
    op.drop_index(op.f("ix_docs_technical_item_documents_id"), table_name="docs_technical_item_documents")
    op.drop_table("docs_technical_item_documents")

    op.drop_index(op.f("ix_docs_technical_items_name"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_status"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_source_system"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_part_number"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_model"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_manufacturer_code"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_manufacturer"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_item_id"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_id"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_equipment_family"), table_name="docs_technical_items")
    op.drop_index(op.f("ix_docs_technical_items_category"), table_name="docs_technical_items")
    op.drop_table("docs_technical_items")

    op.execute("DROP TYPE IF EXISTS technical_item_document_relation_type")
