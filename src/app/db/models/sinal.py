from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SinalModel(Base):
    __tablename__ = "sinais"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    regra_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    data_ativacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contexto: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_desativacao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
