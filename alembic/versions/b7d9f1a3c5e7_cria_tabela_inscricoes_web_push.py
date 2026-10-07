"""cria tabela inscricoes_web_push

Revision ID: b7d9f1a3c5e7
Revises: a3c5e7f9b1d2
Create Date: 2026-10-07 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d9f1a3c5e7"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inscricoes_web_push",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint", sa.String(length=1024), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index("ix_inscricoes_web_push_usuario_id", "inscricoes_web_push", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_inscricoes_web_push_usuario_id", table_name="inscricoes_web_push")
    op.drop_table("inscricoes_web_push")
