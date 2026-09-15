"""cria tabela alertas_personalizados

Revision ID: d29b7e14a6f3
Revises: c4d8e6f1a293
Create Date: 2026-09-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d29b7e14a6f3"
down_revision: str | Sequence[str] | None = "c4d8e6f1a293"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alertas_personalizados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo_condicao", sa.String(length=30), nullable=False),
        sa.Column("valor_alvo", sa.Numeric(18, 6), nullable=False),
        sa.Column("moeda_alvo", sa.String(length=3), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("ultimo_estado", sa.Boolean(), nullable=False),
        sa.Column("disparado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["ativo_id"], ["ativos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alertas_personalizados")
