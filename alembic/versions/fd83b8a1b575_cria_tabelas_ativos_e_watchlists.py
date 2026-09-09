"""cria tabelas ativos e watchlists

Revision ID: fd83b8a1b575
Revises: ff80ce5f5e3c
Create Date: 2026-09-09 11:31:49.169856

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "fd83b8a1b575"
down_revision: str | Sequence[str] | None = "ff80ce5f5e3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ativos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("setor", sa.String(length=255), nullable=True),
        sa.Column("moeda", sa.String(length=10), nullable=False),
        sa.Column("fonte_dados", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker"),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("adicionado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notificar", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "ativo_id"),
    )


def downgrade() -> None:
    op.drop_table("watchlists")
    op.drop_table("ativos")
