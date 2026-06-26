"""add work orders

Revision ID: 0006_work_orders
Revises: 0005_docs
Create Date: 2026-06-05 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_work_orders"
down_revision: Union[str, None] = "0005_docs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


work_order_priority = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="work_order_priority",
    create_type=False,
)
work_order_status = postgresql.ENUM(
    "open",
    "assigned",
    "in_progress",
    "completed",
    "cancelled",
    name="work_order_status",
    create_type=False,
)


def _create_enums() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE work_order_priority AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE work_order_status AS ENUM (
                'open',
                'assigned',
                'in_progress',
                'completed',
                'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", work_order_priority, nullable=False),
        sa.Column("status", work_order_status, nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_work_orders_asset_id"), "work_orders", ["asset_id"], unique=False)
    op.create_index(op.f("ix_work_orders_assigned_user_id"), "work_orders", ["assigned_user_id"], unique=False)
    op.create_index(op.f("ix_work_orders_created_by"), "work_orders", ["created_by"], unique=False)
    op.create_index(op.f("ix_work_orders_due_date"), "work_orders", ["due_date"], unique=False)
    op.create_index(op.f("ix_work_orders_id"), "work_orders", ["id"], unique=False)
    op.create_index(op.f("ix_work_orders_priority"), "work_orders", ["priority"], unique=False)
    op.create_index(op.f("ix_work_orders_status"), "work_orders", ["status"], unique=False)
    op.create_index(op.f("ix_work_orders_title"), "work_orders", ["title"], unique=False)

    op.add_column("interventions", sa.Column("work_order_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_interventions_work_order_id"), "interventions", ["work_order_id"], unique=False)
    op.create_foreign_key(
        "fk_interventions_work_order_id_work_orders",
        "interventions",
        "work_orders",
        ["work_order_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_interventions_work_order_id_work_orders", "interventions", type_="foreignkey")
    op.drop_index(op.f("ix_interventions_work_order_id"), table_name="interventions")
    op.drop_column("interventions", "work_order_id")

    op.drop_index(op.f("ix_work_orders_title"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_status"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_priority"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_id"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_due_date"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_created_by"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_assigned_user_id"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_asset_id"), table_name="work_orders")
    op.drop_table("work_orders")

    op.execute("DROP TYPE IF EXISTS work_order_status")
    op.execute("DROP TYPE IF EXISTS work_order_priority")
