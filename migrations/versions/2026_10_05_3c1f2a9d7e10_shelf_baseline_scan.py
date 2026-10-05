"""shelf baseline scan

Revision ID: 3c1f2a9d7e10
Revises: 84e6688cf595
Create Date: 2026-10-05 12:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c1f2a9d7e10"
down_revision: str | Sequence[str] | None = "84e6688cf595"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK = "fk_shelves_baseline_scan_id_scans"


def upgrade() -> None:
    # nullable, no default: adding it is instant and every existing shelf has no baseline
    with op.batch_alter_table("shelves", schema=None) as batch_op:
        batch_op.add_column(sa.Column("baseline_scan_id", sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(FK, "scans", ["baseline_scan_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("shelves", schema=None) as batch_op:
        batch_op.drop_constraint(FK, type_="foreignkey")
        batch_op.drop_column("baseline_scan_id")
