"""add missing intervention fields

Revision ID: 0002_add_fields
Revises: 0001_initial
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_fields"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("interventions", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column("intervention_assets", sa.Column("location_note", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("intervention_assets", "location_note")
    op.drop_column("interventions", "end_date")
