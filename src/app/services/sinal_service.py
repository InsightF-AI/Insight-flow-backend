from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_indicador import TipoIndicador
from app.domain.regras_sinal_padrao import REGRAS_PADRAO, buscar_regra_por_id
from app.domain.value_objects.resultado_backtest import ResultadoBacktest
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.services.exceptions import AtivoNaoEncontradoError, RegraNaoEncontradaError
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

    def backtest(self, regra_id: UUID, ativo_id: UUID) -> ResultadoBacktest:
        ativo = self._buscar_ativo(ativo_id)
        regra = buscar_regra_por_id(regra_id)
        if regra is None:
            raise RegraNaoEncontradaError(regra_id)

        cotacoes = self._cotacao_repository.listar_por_ativo(ativo.id)
        corte = datetime.now(UTC) - timedelta(days=730)

        metodo_calculo = {
            TipoIndicador.SMA: self._indicador_service.calcular_sma,
            TipoIndicador.RSI: self._indicador_service.calcular_rsi,
            TipoIndicador.MACD: self._indicador_service.calcular_macd,
            TipoIndicador.BOLLINGER: self._indicador_service.calcular_bollinger,
            TipoIndicador.VOLUME_RELATIVO: self._indicador_service.calcular_volume_relativo,
        }[TipoIndicador(regra.condicoes["tipo_indicador"])]
        parametros = regra.condicoes["parametros"]

        ocorrencias: list[int] = []
        satisfeita_anterior = False
        for i, cotacao in enumerate(cotacoes):
            indicador = metodo_calculo(cotacoes[: i + 1], **parametros)
            satisfeita = indicador is not None and avaliar_condicao(
                regra.condicoes, indicador.valor
            )
            if cotacao.data_hora >= corte and satisfeita and not satisfeita_anterior:
                ocorrencias.append(i)
            satisfeita_anterior = satisfeita

        retornos: dict[int, list[Decimal]] = {5: [], 20: [], 60: []}
        for i in ocorrencias:
            preco_base = cotacoes[i].fechamento
            for janela in (5, 20, 60):
                if i + janela < len(cotacoes):
                    preco_futuro = cotacoes[i + janela].fechamento
                    retornos[janela].append((preco_futuro / preco_base - 1) * 100)

        def _media(valores: list[Decimal]) -> Decimal | None:
            return sum(valores) / len(valores) if valores else None

        return ResultadoBacktest(
            regra_id=regra.id,
            ativo_id=ativo.id,
            total_ocorrencias=len(ocorrencias),
            retorno_medio_5_pregoes=_media(retornos[5]),
            retorno_medio_20_pregoes=_media(retornos[20]),
            retorno_medio_60_pregoes=_media(retornos[60]),
        )

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
