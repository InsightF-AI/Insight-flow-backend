"""cria tabela refresh_tokens

Revision ID: f1a7c3e9b2d4
Revises: c9e3a5b7d1f2
Create Date: 2026-10-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a7c3e9b2d4"
down_revision: str | Sequence[str] | None = "c9e3a5b7d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("familia_id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_familia_id", "refresh_tokens", ["familia_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_familia_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
