"""initial schema - create all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from sqlalchemy.dialects import postgresql
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ENUMS ---
    sa.Enum(
        "available", "in_use", "maintenance", "retired", "unknown",
        name="asset_status"
    ).create(op.get_bind(), checkfirst=True)

    sa.Enum(
        "installation", "support", "maintenance", "inspection", "removal", "other",
        name="intervention_type"
    ).create(op.get_bind(), checkfirst=True)

    asset_status_enum = postgresql.ENUM(
        "available", "in_use", "maintenance", "retired", "unknown",
        name="asset_status",
        create_type=False
    )

    intervention_type_enum = postgresql.ENUM(
        "installation", "support", "maintenance", "inspection", "removal", "other",
        name="intervention_type",
        create_type=False
    )

    # --- PARTS ---
    op.create_table(
        "parts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("part_number", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parts_id", "parts", ["id"])
    op.create_index("ix_parts_part_number", "parts", ["part_number"], unique=True)

    # --- ASSETS ---
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.String(length=150), nullable=True),
        sa.Column("internal_code", sa.String(length=150), nullable=True),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("status", asset_status_enum, nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["part_id"], ["parts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_id", "assets", ["id"])
    op.create_index("ix_assets_part_id", "assets", ["part_id"])
    op.create_index("ix_assets_serial_number", "assets", ["serial_number"], unique=True)
    op.create_index("ix_assets_internal_code", "assets", ["internal_code"], unique=True)

    # --- INTERVENTIONS ---
    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", intervention_type_enum, nullable=False),
        sa.Column("rig", sa.String(length=150), nullable=False),
        sa.Column("pozo", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("technician", sa.String(length=200), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interventions_id", "interventions", ["id"])
    op.create_index("ix_interventions_rig", "interventions", ["rig"])
    op.create_index("ix_interventions_pozo", "interventions", ["pozo"])

    # --- INTERVENTION_ASSETS ---
    op.create_table(
        "intervention_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("intervention_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_intervention_assets_id", "intervention_assets", ["id"])
    op.create_index("ix_intervention_assets_intervention_id", "intervention_assets", ["intervention_id"])
    op.create_index("ix_intervention_assets_asset_id", "intervention_assets", ["asset_id"])

    # --- EVIDENCES ---
    op.create_table(
        "evidences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("intervention_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidences_id", "evidences", ["id"])
    op.create_index("ix_evidences_intervention_id", "evidences", ["intervention_id"])


def downgrade() -> None:
    op.drop_table("evidences")
    op.drop_table("intervention_assets")
    op.drop_table("interventions")
    op.drop_table("assets")
    op.drop_table("parts")

    op.execute("DROP TYPE IF EXISTS intervention_type")
    op.execute("DROP TYPE IF EXISTS asset_status")
