"""cria tabela indicadores_tecnicos

Revision ID: b8c1d3e9f2a7
Revises: a3f7c9e21d84
Create Date: 2026-09-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c1d3e9f2a7"
down_revision: str | Sequence[str] | None = "a3f7c9e21d84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indicadores_tecnicos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("chave", sa.String(length=50), nullable=False),
        sa.Column("data_calculo", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valor", sa.Numeric(18, 6), nullable=False),
        sa.Column("valores_auxiliares", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ativo_id", "chave"),
    )


def downgrade() -> None:
    op.drop_table("indicadores_tecnicos")
