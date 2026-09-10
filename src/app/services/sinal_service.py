from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_indicador import TipoIndicador
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.indicador_service import IndicadorService

_OPERADORES: dict[str, Callable[[Decimal, Decimal], bool]] = {
    "menor_que": lambda valor, limiar: valor < limiar,
    "maior_que": lambda valor, limiar: valor > limiar,
    "menor_igual": lambda valor, limiar: valor <= limiar,
    "maior_igual": lambda valor, limiar: valor >= limiar,
}


def avaliar_condicao(condicoes: dict, valor: Decimal) -> bool:
    operador = _OPERADORES[condicoes["operador"]]
    limiar = Decimal(str(condicoes["valor_limiar"]))
    return operador(valor, limiar)


def _encontrar_indicador(
    indicadores: list[IndicadorTecnico], condicoes: dict
) -> IndicadorTecnico | None:
    tipo = TipoIndicador(condicoes["tipo_indicador"])
    parametros = condicoes["parametros"]
    for indicador in indicadores:
        if indicador.tipo == tipo and indicador.parametros == parametros:
            return indicador
    return None


class SinalService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        cotacao_repository: CotacaoRepository,
        indicador_service: IndicadorService,
        sinal_repository: SinalRepository,
    ):
        self._ativo_repository = ativo_repository
        self._cotacao_repository = cotacao_repository
        self._indicador_service = indicador_service
        self._sinal_repository = sinal_repository

    def avaliar_ativo(self, ativo_id: UUID) -> list[Sinal]:
        ativo = self._buscar_ativo(ativo_id)
        indicadores = self._indicador_service.calcular_todos(ativo.id)
        vigentes: list[Sinal] = []
        for regra in REGRAS_PADRAO:
            if not regra.ativa:
                continue
            indicador = _encontrar_indicador(indicadores, regra.condicoes)
            satisfeita = indicador is not None and avaliar_condicao(
                regra.condicoes, indicador.valor
            )
            sinal_existente = self._sinal_repository.buscar_ativo(ativo.id, regra.id)
            if satisfeita and sinal_existente is None:
                novo = Sinal(
                    id=uuid4(),
                    ativo_id=ativo.id,
                    regra_id=regra.id,
                    data_ativacao=datetime.now(UTC),
                    contexto={"valor": str(indicador.valor)},
                    data_desativacao=None,
                )
                self._sinal_repository.salvar(novo)
                vigentes.append(novo)
            elif not satisfeita and sinal_existente is not None:
                sinal_existente.data_desativacao = datetime.now(UTC)
                self._sinal_repository.salvar(sinal_existente)
            elif satisfeita and sinal_existente is not None:
                vigentes.append(sinal_existente)
        return vigentes

    def score_composto(self, ativo_id: UUID) -> Decimal:
        ativo = self._buscar_ativo(ativo_id)
        total = Decimal(0)
        for regra in REGRAS_PADRAO:
            if self._sinal_repository.buscar_ativo(ativo.id, regra.id) is not None:
                total += regra.peso
        return total

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
