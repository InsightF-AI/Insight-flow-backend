from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WatchlistModel(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("usuario_id", "ativo_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=False)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    adicionado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notificar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
