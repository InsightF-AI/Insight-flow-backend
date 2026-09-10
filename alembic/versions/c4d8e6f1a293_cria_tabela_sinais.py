"""cria tabela sinais

Revision ID: c4d8e6f1a293
Revises: b8c1d3e9f2a7
Create Date: 2026-09-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d8e6f1a293"
down_revision: str | Sequence[str] | None = "b8c1d3e9f2a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sinais",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("regra_id", sa.Uuid(), nullable=False),
        sa.Column("data_ativacao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contexto", sa.JSON(), nullable=False),
        sa.Column("data_desativacao", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sinais")
