from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.ativo import AtivoModel
from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.interfaces.ativo_repository import AtivoRepository


class SqlAlchemyAtivoRepository(AtivoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, ativo: Ativo) -> None:
        modelo = self._session.get(AtivoModel, ativo.id)
        if modelo is None:
            modelo = AtivoModel(id=ativo.id)
            self._session.add(modelo)

        modelo.ticker = ativo.ticker
        modelo.nome = ativo.nome
        modelo.tipo = ativo.tipo
        modelo.setor = ativo.setor
        modelo.moeda = ativo.moeda
        modelo.fonte_dados = ativo.fonte_dados
        self._session.commit()

    def buscar_por_id(self, id: UUID) -> Ativo | None:
        modelo = self._session.get(AtivoModel, id)
        return self._para_entidade(modelo) if modelo is not None else None

    def buscar_por_ticker(self, ticker: str) -> Ativo | None:
        modelo = self._session.scalar(select(AtivoModel).where(AtivoModel.ticker == ticker))
        return self._para_entidade(modelo) if modelo is not None else None

    @staticmethod
    def _para_entidade(modelo: AtivoModel) -> Ativo:
        return Ativo(
            id=modelo.id,
            ticker=modelo.ticker,
            nome=modelo.nome,
            tipo=TipoAtivo(modelo.tipo),
            setor=modelo.setor,
            moeda=modelo.moeda,
            fonte_dados=modelo.fonte_dados,
        )
