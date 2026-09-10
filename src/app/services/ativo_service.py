from __future__ import annotations

from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AtivoNaoEncontradoError


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
        pontos = self._dados_mercado_service.buscar_historico(ativo.ticker, periodo)
        self._cotacao_repository.salvar_muitas(
            [self._para_cotacao(ativo.id, ponto) for ponto in pontos]
        )
        return pontos

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
