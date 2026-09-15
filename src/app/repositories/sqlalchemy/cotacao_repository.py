from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.cotacao import CotacaoModel
from app.domain.entities.cotacao import Cotacao
from app.repositories.interfaces.cotacao_repository import CotacaoRepository


class SqlAlchemyCotacaoRepository(CotacaoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar_muitas(self, cotacoes: list[Cotacao]) -> None:
        if not cotacoes:
            return

        por_chave: dict[tuple, Cotacao] = {
            (cotacao.ativo_id, cotacao.data_hora): cotacao for cotacao in cotacoes
        }
        valores = [
            {
                "id": cotacao.id,
                "ativo_id": cotacao.ativo_id,
                "data_hora": cotacao.data_hora,
                "abertura": cotacao.abertura,
                "maxima": cotacao.maxima,
                "minima": cotacao.minima,
                "fechamento": cotacao.fechamento,
                "volume": cotacao.volume,
            }
            for cotacao in por_chave.values()
        ]
        stmt = insert(CotacaoModel).values(valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "data_hora"],
            set_={
                "abertura": stmt.excluded.abertura,
                "maxima": stmt.excluded.maxima,
                "minima": stmt.excluded.minima,
                "fechamento": stmt.excluded.fechamento,
                "volume": stmt.excluded.volume,
            },
        )
        self._session.execute(stmt)
        self._session.commit()

    def listar_por_ativo(self, ativo_id: UUID) -> list[Cotacao]:
        modelos = self._session.scalars(
            select(CotacaoModel)
            .where(CotacaoModel.ativo_id == ativo_id)
            .order_by(CotacaoModel.data_hora)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: CotacaoModel) -> Cotacao:
        return Cotacao(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            data_hora=modelo.data_hora,
            abertura=modelo.abertura,
            maxima=modelo.maxima,
            minima=modelo.minima,
            fechamento=modelo.fechamento,
            volume=modelo.volume,
        )
