"""torna notificacao ativo_id opcional

Revision ID: c9e3a5b7d1f2
Revises: b7d2e4a1c953
Create Date: 2026-09-29 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9e3a5b7d1f2"
down_revision: str | Sequence[str] | None = "b7d2e4a1c953"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("notificacoes", "ativo_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM notificacoes WHERE ativo_id IS NULL")
    op.alter_column("notificacoes", "ativo_id", existing_type=sa.Uuid(), nullable=False)
