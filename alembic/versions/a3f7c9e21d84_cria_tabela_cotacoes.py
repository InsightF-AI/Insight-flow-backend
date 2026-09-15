"""cria tabela cotacoes

Revision ID: a3f7c9e21d84
Revises: fd83b8a1b575
Create Date: 2026-09-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f7c9e21d84"
down_revision: str | Sequence[str] | None = "fd83b8a1b575"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cotacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("data_hora", sa.DateTime(timezone=True), nullable=False),
        sa.Column("abertura", sa.Numeric(18, 6), nullable=False),
        sa.Column("maxima", sa.Numeric(18, 6), nullable=False),
        sa.Column("minima", sa.Numeric(18, 6), nullable=False),
        sa.Column("fechamento", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.Numeric(20, 6), nullable=False),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ativo_id", "data_hora"),
    )


def downgrade() -> None:
    op.drop_table("cotacoes")
