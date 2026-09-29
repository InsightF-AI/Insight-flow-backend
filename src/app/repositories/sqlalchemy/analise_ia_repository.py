from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.analise_ia import AnaliseIAModel
from app.domain.entities.analise_ia import AnaliseIA
from app.repositories.interfaces.analise_ia_repository import AnaliseIARepository


class SqlAlchemyAnaliseIARepository(AnaliseIARepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, analise: AnaliseIA) -> None:
        modelo = self._session.get(AnaliseIAModel, analise.id)
        if modelo is None:
            modelo = AnaliseIAModel(id=analise.id)
            self._session.add(modelo)

        modelo.ativo_id = analise.ativo_id
        modelo.texto = analise.texto
        modelo.provedor = analise.provedor
        modelo.modelo = analise.modelo
        modelo.prompt_versao = analise.prompt_versao
        modelo.contexto_hash = analise.contexto_hash
        modelo.gerado_em = analise.gerado_em
        self._session.commit()

    def buscar_ultima_por_ativo(self, ativo_id: UUID) -> AnaliseIA | None:
        modelo = self._session.scalars(
            select(AnaliseIAModel)
            .where(AnaliseIAModel.ativo_id == ativo_id)
            .order_by(AnaliseIAModel.gerado_em.desc())
            .limit(1)
        ).first()
        return self._para_entidade(modelo) if modelo is not None else None

    @staticmethod
    def _para_entidade(modelo: AnaliseIAModel) -> AnaliseIA:
        return AnaliseIA(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            texto=modelo.texto,
            provedor=modelo.provedor,
            modelo=modelo.modelo,
            prompt_versao=modelo.prompt_versao,
            contexto_hash=modelo.contexto_hash,
            gerado_em=modelo.gerado_em,
        )
