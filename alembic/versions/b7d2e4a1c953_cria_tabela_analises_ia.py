"""cria tabela analises_ia

Revision ID: b7d2e4a1c953
Revises: 7e2a9c4b1f06
Create Date: 2026-09-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d2e4a1c953"
down_revision: str | Sequence[str] | None = "7e2a9c4b1f06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analises_ia",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("provedor", sa.String(length=30), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("prompt_versao", sa.String(length=50), nullable=False),
        sa.Column("contexto_hash", sa.String(length=64), nullable=False),
        sa.Column("gerado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ativo_id"], ["ativos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analises_ia_ativo_id_gerado_em", "analises_ia", ["ativo_id", "gerado_em"]
    )


def downgrade() -> None:
    op.drop_index("ix_analises_ia_ativo_id_gerado_em", table_name="analises_ia")
    op.drop_table("analises_ia")
