from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndicadorTecnicoModel(Base):
    __tablename__ = "indicadores_tecnicos"
    __table_args__ = (UniqueConstraint("ativo_id", "chave"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    parametros: Mapped[dict] = mapped_column(JSON, nullable=False)
    chave: Mapped[str] = mapped_column(String(50), nullable=False)
    data_calculo: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    valores_auxiliares: Mapped[dict | None] = mapped_column(JSON, nullable=True)
