from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificacaoModel(Base):
    __tablename__ = "notificacoes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=False)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    mensagem: Mapped[str] = mapped_column(String(255), nullable=False)
    contexto: Mapped[dict] = mapped_column(JSON, nullable=False)
    lida: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
