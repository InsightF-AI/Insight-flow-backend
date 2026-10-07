from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InscricaoWebPushModel(Base):
    __tablename__ = "inscricoes_web_push"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
