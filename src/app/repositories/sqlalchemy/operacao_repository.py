from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.operacao import OperacaoModel
from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.repositories.interfaces.operacao_repository import OperacaoRepository


class SqlAlchemyOperacaoRepository(OperacaoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, operacao: Operacao) -> None:
        modelo = self._session.get(OperacaoModel, operacao.id)
        if modelo is None:
            modelo = OperacaoModel(id=operacao.id)
            self._session.add(modelo)

        modelo.usuario_id = operacao.usuario_id
        modelo.ativo_id = operacao.ativo_id
        modelo.tipo = operacao.tipo
        modelo.quantidade = operacao.quantidade
        modelo.preco_unitario = operacao.preco_unitario
        modelo.data = operacao.data
        modelo.criado_em = operacao.criado_em
        self._session.commit()

    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None:
        modelo = self._session.get(OperacaoModel, operacao_id)
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]:
        modelos = self._session.scalars(
            select(OperacaoModel).where(OperacaoModel.usuario_id == usuario_id)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    def remover(self, operacao: Operacao) -> None:
        modelo = self._session.get(OperacaoModel, operacao.id)
        if modelo is not None:
            self._session.delete(modelo)
            self._session.commit()

    @staticmethod
    def _para_entidade(modelo: OperacaoModel) -> Operacao:
        return Operacao(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            ativo_id=modelo.ativo_id,
            tipo=TipoOperacao(modelo.tipo),
            quantidade=modelo.quantidade,
            preco_unitario=modelo.preco_unitario,
            data=modelo.data,
            criado_em=modelo.criado_em,
        )
