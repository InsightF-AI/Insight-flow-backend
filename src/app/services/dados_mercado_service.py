from __future__ import annotations

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import AtivoEncontrado, BrapiClient, CotacaoAtual, PontoHistorico


class DadosMercadoService:
    def __init__(self, brapi_client: BrapiClient):
        self._brapi_client = brapi_client

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        return self._brapi_client.buscar_ativos(termo)

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        return self._brapi_client.buscar_cotacao_atual(ticker)

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        return self._brapi_client.buscar_historico(ticker, periodo)
