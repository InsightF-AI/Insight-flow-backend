from __future__ import annotations

from uuid import UUID

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums.tipo_ativo import TipoAtivo


class AtivoModel(Base):
    __tablename__ = "ativos"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[TipoAtivo] = mapped_column(String(20), nullable=False)
    setor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    moeda: Mapped[str] = mapped_column(String(10), nullable=False)
    fonte_dados: Mapped[str] = mapped_column(String(50), nullable=False)
