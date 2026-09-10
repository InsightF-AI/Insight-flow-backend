from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.dados_mercado_service import DadosMercadoService
from app.services.mercado_cache import MercadoCache


class CachedDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        interno: DadosMercadoService,
        cache: MercadoCache,
        ttl_cotacao_atual: int,
    ):
        self._interno = interno
        self._cache = cache
        self._ttl_cotacao_atual = ttl_cotacao_atual

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        return self._interno.buscar_ativo(termo)

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        chave = f"cotacao_atual:{ticker}"
        em_cache = self._cache.obter(chave)
        if em_cache is not None:
            return _cotacao_atual_de_json(em_cache)

        cotacao = self._interno.buscar_cotacao_atual(ticker)
        self._cache.salvar(chave, _cotacao_atual_para_json(cotacao), self._ttl_cotacao_atual)
        return cotacao

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        chave = f"historico:{ticker}:{periodo.value}"
        em_cache = self._cache.obter(chave)
        if em_cache is not None:
            return _historico_de_json(em_cache)

        pontos = self._interno.buscar_historico(ticker, periodo)
        self._cache.salvar(chave, _historico_para_json(pontos), self._ttl_cotacao_atual)
        return pontos


def _cotacao_atual_para_json(cotacao: CotacaoAtual) -> str:
    return json.dumps(
        {
            "ticker": cotacao.ticker,
            "preco": str(cotacao.preco),
            "variacao": str(cotacao.variacao),
            "variacao_percentual": str(cotacao.variacao_percentual),
            "maxima_dia": str(cotacao.maxima_dia),
            "minima_dia": str(cotacao.minima_dia),
            "volume": str(cotacao.volume),
        }
    )


def _cotacao_atual_de_json(bruto: str) -> CotacaoAtual:
    dados = json.loads(bruto)
    return CotacaoAtual(
        ticker=dados["ticker"],
        preco=Decimal(dados["preco"]),
        variacao=Decimal(dados["variacao"]),
        variacao_percentual=Decimal(dados["variacao_percentual"]),
        maxima_dia=Decimal(dados["maxima_dia"]),
        minima_dia=Decimal(dados["minima_dia"]),
        volume=Decimal(dados["volume"]),
    )


def _ponto_historico_para_dict(ponto: PontoHistorico) -> dict:
    return {
        "data": ponto.data.isoformat(),
        "abertura": str(ponto.abertura),
        "maxima": str(ponto.maxima),
        "minima": str(ponto.minima),
        "fechamento": str(ponto.fechamento),
        "volume": str(ponto.volume),
    }


def _ponto_historico_de_dict(dados: dict) -> PontoHistorico:
    return PontoHistorico(
        data=datetime.fromisoformat(dados["data"]),
        abertura=Decimal(dados["abertura"]),
        maxima=Decimal(dados["maxima"]),
        minima=Decimal(dados["minima"]),
        fechamento=Decimal(dados["fechamento"]),
        volume=Decimal(dados["volume"]),
    )


def _historico_para_json(pontos: list[PontoHistorico]) -> str:
    return json.dumps([_ponto_historico_para_dict(ponto) for ponto in pontos])


def _historico_de_json(bruto: str) -> list[PontoHistorico]:
    return [_ponto_historico_de_dict(item) for item in json.loads(bruto)]
