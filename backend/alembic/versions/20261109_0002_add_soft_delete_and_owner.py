"""Add owner_id, is_deleted, deleted_at and update unique partial index.

Revision ID: 20261109_0002
Revises: 20261007_0001
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261109_0002"
down_revision: str | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add owner_id as nullable first, populate from customer_name to prevent shared anonymous ownership, then make NOT NULL
    op.add_column(
        "appointments",
        sa.Column(
            "owner_id",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.execute("UPDATE appointments SET owner_id = customer_name WHERE owner_id IS NULL")
    op.alter_column(
        "appointments",
        "owner_id",
        nullable=False,
        server_default=sa.text("'unassigned'"),
    )

    # 2. Add soft delete flags
    op.add_column(
        "appointments",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Recreate partial unique index to exclude soft-deleted records
    op.drop_index("uq_appointments_active_starts_at", table_name="appointments")
    op.create_index(
        "uq_appointments_active_starts_at",
        "appointments",
        ["starts_at"],
        unique=True,
        postgresql_where=sa.text("status = 'booked' AND is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("uq_appointments_active_starts_at", table_name="appointments")
    op.create_index(
        "uq_appointments_active_starts_at",
        "appointments",
        ["starts_at"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
    )
    op.drop_column("appointments", "deleted_at")
    op.drop_column("appointments", "is_deleted")
    op.drop_column("appointments", "owner_id")

