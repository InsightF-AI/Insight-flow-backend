from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.politica_historico import PoliticaHistorico
from app.integrations.brapi.client import (
    CotacaoAtual,
    PontoHistorico,
)
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AtivoNaoEncontradoError

_DIAS_POR_PERIODO = {
    PeriodoHistorico.UMA_SEMANA: 7,
    PeriodoHistorico.UM_MES: 30,
    PeriodoHistorico.TRES_MESES: 90,
    PeriodoHistorico.UM_ANO: 365,
    PeriodoHistorico.CINCO_ANOS: 1825,
}

_PERIODO_DE_COLETA = {
    PeriodoHistorico.UMA_SEMANA: PeriodoHistorico.UMA_SEMANA,
    PeriodoHistorico.UM_MES: PeriodoHistorico.UM_MES,
    PeriodoHistorico.TRES_MESES: PeriodoHistorico.TRES_MESES,
    PeriodoHistorico.UM_ANO: PeriodoHistorico.TRES_MESES,
    PeriodoHistorico.CINCO_ANOS: PeriodoHistorico.TRES_MESES,
}


class AtivoService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
        cotacao_repository: CotacaoRepository,
    ):
        self._ativo_repository = ativo_repository
        self._dados_mercado_service = dados_mercado_service
        self._cotacao_repository = cotacao_repository

    def cotacao_atual(self, ativo_id: UUID) -> CotacaoAtual:
        ativo = self._buscar_ativo(ativo_id)
        return self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)

    def historico(self, ativo_id: UUID, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        ativo = self._buscar_ativo(ativo_id)
        if periodo == PeriodoHistorico.UM_DIA:
            return [self._ponto_do_dia(ativo)]
        coleta = _PERIODO_DE_COLETA[periodo]
        self._coletar_historico(ativo, coleta)
        if coleta != PeriodoHistorico.UMA_SEMANA:
            self._coletar_historico(ativo, PeriodoHistorico.UMA_SEMANA)
        desde = datetime.now(UTC) - timedelta(days=_DIAS_POR_PERIODO[periodo])
        return self._historico_persistido(ativo.id, desde)

    def buscar_ou_criar_indice(self, ticker: str, nome: str) -> Ativo:
        ativo = self._ativo_repository.buscar_por_ticker(ticker)
        if ativo is not None:
            return ativo
        ativo = Ativo(
            id=uuid4(),
            ticker=ticker,
            nome=nome,
            tipo=TipoAtivo.INDICE,
            setor=None,
            moeda="BRL",
            fonte_dados="brapi",
        )
        self._ativo_repository.salvar(ativo)
        return ativo

    def atualizar_historico(self, ativo_id: UUID, politica: PoliticaHistorico) -> None:
        ativo = self._buscar_ativo(ativo_id)
        persistidas = len(self._cotacao_repository.listar_por_ativo(ativo.id))
        periodo = (
            politica.periodo_backfill_de(ativo.tipo)
            if persistidas < politica.minimo_cotacoes
            else PeriodoHistorico.UMA_SEMANA
        )
        self._coletar_historico(ativo, periodo)

    def _coletar_historico(self, ativo: Ativo, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        pontos = self._dados_mercado_service.buscar_historico(ativo.ticker, periodo)
        if self._dados_mercado_service.historico_e_diario(ativo.ticker, periodo):
            self._cotacao_repository.salvar_muitas(
                [self._para_cotacao(ativo.id, ponto) for ponto in pontos]
            )
        return pontos

    def _historico_persistido(self, ativo_id: UUID, desde: datetime) -> list[PontoHistorico]:
        return [
            PontoHistorico(
                data=cotacao.data_hora,
                abertura=cotacao.abertura,
                maxima=cotacao.maxima,
                minima=cotacao.minima,
                fechamento=cotacao.fechamento,
                volume=cotacao.volume,
            )
            for cotacao in self._cotacao_repository.listar_por_ativo(ativo_id)
            if cotacao.data_hora >= desde
        ]

    def _ponto_do_dia(self, ativo: Ativo) -> PontoHistorico:
        cotacao = self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)
        return PontoHistorico(
            data=datetime.now(UTC),
            abertura=cotacao.abertura if cotacao.abertura is not None else cotacao.preco,
            maxima=cotacao.maxima_dia,
            minima=cotacao.minima_dia,
            fechamento=cotacao.preco,
            volume=cotacao.volume,
        )

    @staticmethod
    def _para_cotacao(ativo_id: UUID, ponto: PontoHistorico) -> Cotacao:
        return Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=ponto.data,
            abertura=ponto.abertura,
            maxima=ponto.maxima,
            minima=ponto.minima,
            fechamento=ponto.fechamento,
            volume=ponto.volume,
        )

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
