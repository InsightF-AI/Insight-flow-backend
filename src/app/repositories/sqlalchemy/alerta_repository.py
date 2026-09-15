from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.alerta_personalizado import AlertaPersonalizadoModel
from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.repositories.interfaces.alerta_repository import AlertaRepository


class SqlAlchemyAlertaRepository(AlertaRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, alerta: AlertaPersonalizado) -> None:
        modelo = self._session.get(AlertaPersonalizadoModel, alerta.id)
        if modelo is None:
            modelo = AlertaPersonalizadoModel(id=alerta.id)
            self._session.add(modelo)

        modelo.usuario_id = alerta.usuario_id
        modelo.ativo_id = alerta.ativo_id
        modelo.tipo_condicao = alerta.tipo_condicao
        modelo.valor_alvo = alerta.valor_alvo
        modelo.moeda_alvo = alerta.moeda_alvo
        modelo.ativo = alerta.ativo
        modelo.ultimo_estado = alerta.ultimo_estado
        modelo.disparado_em = alerta.disparado_em
        modelo.criado_em = alerta.criado_em
        modelo.atualizado_em = alerta.atualizado_em
        self._session.commit()

    def buscar_por_id(self, alerta_id: UUID) -> AlertaPersonalizado | None:
        modelo = self._session.get(AlertaPersonalizadoModel, alerta_id)
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_usuario(self, usuario_id: UUID) -> list[AlertaPersonalizado]:
        modelos = self._session.scalars(
            select(AlertaPersonalizadoModel).where(
                AlertaPersonalizadoModel.usuario_id == usuario_id
            )
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    def listar_ativos_por_ativo(self, ativo_id: UUID) -> list[AlertaPersonalizado]:
        modelos = self._session.scalars(
            select(AlertaPersonalizadoModel).where(
                AlertaPersonalizadoModel.ativo_id == ativo_id,
                AlertaPersonalizadoModel.ativo.is_(True),
            )
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    def remover(self, alerta: AlertaPersonalizado) -> None:
        modelo = self._session.get(AlertaPersonalizadoModel, alerta.id)
        if modelo is not None:
            self._session.delete(modelo)
            self._session.commit()

    @staticmethod
    def _para_entidade(modelo: AlertaPersonalizadoModel) -> AlertaPersonalizado:
        return AlertaPersonalizado(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            ativo_id=modelo.ativo_id,
            tipo_condicao=TipoCondicaoAlerta(modelo.tipo_condicao),
            valor_alvo=modelo.valor_alvo,
            moeda_alvo=modelo.moeda_alvo,
            criado_em=modelo.criado_em,
            atualizado_em=modelo.atualizado_em,
            ativo=modelo.ativo,
            ultimo_estado=modelo.ultimo_estado,
            disparado_em=modelo.disparado_em,
        )
