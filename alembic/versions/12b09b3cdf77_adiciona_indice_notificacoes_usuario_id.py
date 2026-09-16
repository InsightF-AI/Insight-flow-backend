"""adiciona indice notificacoes usuario_id

Revision ID: 12b09b3cdf77
Revises: e5f9a2c7b104
Create Date: 2026-09-16 13:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "12b09b3cdf77"
down_revision: str | Sequence[str] | None = "e5f9a2c7b104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_notificacoes_usuario_id", "notificacoes", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_notificacoes_usuario_id", table_name="notificacoes")
