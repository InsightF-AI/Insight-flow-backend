"""cria tabelas dispositivos_push e tickets_push

Revision ID: a3c5e7f9b1d2
Revises: f1a7c3e9b2d4
Create Date: 2026-10-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c5e7f9b1d2"
down_revision: str | Sequence[str] | None = "f1a7c3e9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dispositivos_push",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        "ix_dispositivos_push_usuario_ativo", "dispositivos_push", ["usuario_id", "ativo"]
    )
    op.create_table(
        "tickets_push",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_push_criado_em", "tickets_push", ["criado_em"])


def downgrade() -> None:
    op.drop_index("ix_tickets_push_criado_em", table_name="tickets_push")
    op.drop_table("tickets_push")
    op.drop_index("ix_dispositivos_push_usuario_ativo", table_name="dispositivos_push")
    op.drop_table("dispositivos_push")
