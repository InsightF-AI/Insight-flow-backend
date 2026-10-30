"""une as migrations de auditoria e do catalogo de ativos

Revision ID: d5f1b3a7c9e2
Revises: c2e8a4f6b913, 4c8e1a7f2b90
Create Date: 2026-10-30 15:00:00.000000

"""

from collections.abc import Sequence

revision: str = "d5f1b3a7c9e2"
down_revision: str | Sequence[str] | None = ("c2e8a4f6b913", "4c8e1a7f2b90")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
