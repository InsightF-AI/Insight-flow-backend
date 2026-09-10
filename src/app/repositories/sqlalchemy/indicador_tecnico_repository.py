from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.indicador_tecnico import IndicadorTecnicoModel
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository


def _chave_de(tipo: TipoIndicador, parametros: dict) -> str:
    partes = "_".join(f"{chave}={valor}" for chave, valor in sorted(parametros.items()))
    return f"{tipo.value}_{partes}"


class SqlAlchemyIndicadorTecnicoRepository(IndicadorTecnicoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, indicador: IndicadorTecnico) -> None:
        chave = _chave_de(indicador.tipo, indicador.parametros)
        stmt = insert(IndicadorTecnicoModel).values(
            id=indicador.id,
            ativo_id=indicador.ativo_id,
            tipo=indicador.tipo.value,
            parametros=indicador.parametros,
            chave=chave,
            data_calculo=indicador.data_calculo,
            valor=indicador.valor,
            valores_auxiliares=indicador.valores_auxiliares,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "chave"],
            set_={
                "parametros": stmt.excluded.parametros,
                "data_calculo": stmt.excluded.data_calculo,
                "valor": stmt.excluded.valor,
                "valores_auxiliares": stmt.excluded.valores_auxiliares,
            },
        )
        self._session.execute(stmt)
        self._session.commit()

    def salvar_muitas(self, indicadores: list[IndicadorTecnico]) -> None:
        if not indicadores:
            return

        por_chave: dict[tuple, IndicadorTecnico] = {
            (indicador.ativo_id, _chave_de(indicador.tipo, indicador.parametros)): indicador
            for indicador in indicadores
        }
        valores = [
            {
                "id": indicador.id,
                "ativo_id": indicador.ativo_id,
                "tipo": indicador.tipo.value,
                "parametros": indicador.parametros,
                "chave": _chave_de(indicador.tipo, indicador.parametros),
                "data_calculo": indicador.data_calculo,
                "valor": indicador.valor,
                "valores_auxiliares": indicador.valores_auxiliares,
            }
            for indicador in por_chave.values()
        ]
        stmt = insert(IndicadorTecnicoModel).values(valores)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "chave"],
            set_={
                "parametros": stmt.excluded.parametros,
                "data_calculo": stmt.excluded.data_calculo,
                "valor": stmt.excluded.valor,
                "valores_auxiliares": stmt.excluded.valores_auxiliares,
            },
        )
        self._session.execute(stmt)
        self._session.commit()

    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]:
        modelos = self._session.scalars(
            select(IndicadorTecnicoModel).where(IndicadorTecnicoModel.ativo_id == ativo_id)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: IndicadorTecnicoModel) -> IndicadorTecnico:
        return IndicadorTecnico(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            tipo=TipoIndicador(modelo.tipo),
            parametros=modelo.parametros,
            data_calculo=modelo.data_calculo,
            valor=modelo.valor,
            valores_auxiliares=modelo.valores_auxiliares,
        )
