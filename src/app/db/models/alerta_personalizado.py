from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta


class AlertaPersonalizadoModel(Base):
    __tablename__ = "alertas_personalizados"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=False)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    tipo_condicao: Mapped[TipoCondicaoAlerta] = mapped_column(String(30), nullable=False)
    valor_alvo: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    moeda_alvo: Mapped[str] = mapped_column(String(3), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    ultimo_estado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disparado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
