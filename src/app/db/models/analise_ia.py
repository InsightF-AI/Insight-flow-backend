from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnaliseIAModel(Base):
    __tablename__ = "analises_ia"
    __table_args__ = (Index("ix_analises_ia_ativo_id_gerado_em", "ativo_id", "gerado_em"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    provedor: Mapped[str] = mapped_column(String(30), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_versao: Mapped[str] = mapped_column(String(50), nullable=False)
    contexto_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
