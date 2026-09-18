"""adiciona indice operacoes usuario_id

Revision ID: 7e2a9c4b1f06
Revises: a1c4f7e9d203
Create Date: 2026-09-18 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7e2a9c4b1f06"
down_revision: str | Sequence[str] | None = "a1c4f7e9d203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_operacoes_usuario_id", "operacoes", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_operacoes_usuario_id", table_name="operacoes")
