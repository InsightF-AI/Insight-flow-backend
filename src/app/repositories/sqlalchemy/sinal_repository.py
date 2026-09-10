from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.sinal import SinalModel
from app.domain.entities.sinal import Sinal
from app.repositories.interfaces.sinal_repository import SinalRepository


class SqlAlchemySinalRepository(SinalRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, sinal: Sinal) -> None:
        modelo = self._session.get(SinalModel, sinal.id)
        if modelo is None:
            modelo = SinalModel(id=sinal.id)
            self._session.add(modelo)

        modelo.ativo_id = sinal.ativo_id
        modelo.regra_id = sinal.regra_id
        modelo.data_ativacao = sinal.data_ativacao
        modelo.contexto = sinal.contexto
        modelo.data_desativacao = sinal.data_desativacao
        self._session.commit()

    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None:
        modelo = self._session.scalar(
            select(SinalModel).where(
                SinalModel.ativo_id == ativo_id,
                SinalModel.regra_id == regra_id,
                SinalModel.data_desativacao.is_(None),
            )
        )
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]:
        modelos = self._session.scalars(
            select(SinalModel)
            .where(SinalModel.ativo_id == ativo_id)
            .order_by(SinalModel.data_ativacao)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: SinalModel) -> Sinal:
        return Sinal(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            regra_id=modelo.regra_id,
            data_ativacao=modelo.data_ativacao,
            contexto=modelo.contexto,
            data_desativacao=modelo.data_desativacao,
        )
