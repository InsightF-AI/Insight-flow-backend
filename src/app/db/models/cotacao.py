from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CotacaoModel(Base):
    __tablename__ = "cotacoes"
    __table_args__ = (UniqueConstraint("ativo_id", "data_hora"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    abertura: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    maxima: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    minima: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fechamento: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
