"""Quarantine all historical ownership, including old name-based owners.

New application writes explicitly enable upstream-asserted ownership. This flag
does not authenticate a caller. Historical rows require verified administrative
reassignment; no client-facing API can enable access to them.
"""

import sqlalchemy as sa

from alembic import op

revision = "20261109_0003"
down_revision = "20261109_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("owner_access_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("appointments", "owner_access_enabled")
