"""cria tabela operacoes

Revision ID: a1c4f7e9d203
Revises: 12b09b3cdf77
Create Date: 2026-09-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c4f7e9d203"
down_revision: str | Sequence[str] | None = "12b09b3cdf77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("quantidade", sa.Numeric(18, 6), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(18, 6), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["ativo_id"], ["ativos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("operacoes")
