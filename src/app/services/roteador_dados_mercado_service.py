from __future__ import annotations

import json
import logging

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.binance.client import BinanceClient, BinanceIndisponivelError
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.dados_mercado_service import DadosMercadoService
from app.services.mercado_cache import MercadoCache

logger = logging.getLogger(__name__)

_CHAVE_CATALOGO = "catalogo_cripto_brl"


class RoteadorDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        brapi: DadosMercadoService,
        binance_client: BinanceClient,
        cache: MercadoCache,
        ttl_catalogo_segundos: int,
    ):
        self._brapi = brapi
        self._binance_client = binance_client
        self._cache = cache
        self._ttl_catalogo_segundos = ttl_catalogo_segundos

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        encontrados = self._brapi.buscar_ativo(termo)
        try:
            catalogo = self._catalogo()
        except BinanceIndisponivelError:
            logger.warning("Binance indisponivel; busca segue apenas com a brapi.")
            return encontrados

        termo_normalizado = termo.upper()
        return encontrados + [
            AtivoEncontrado(
                ticker=codigo,
                nome=codigo,
                tipo=TipoAtivo.CRIPTO,
                moeda="BRL",
                setor=None,
                fonte_dados="binance",
            )
            for codigo in catalogo
            if termo_normalizado in codigo
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self._e_cripto(ticker):
            return self._binance_client.buscar_cotacao_atual(ticker)
        return self._brapi.buscar_cotacao_atual(ticker)

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        if self._e_cripto(ticker):
            return self._binance_client.buscar_historico(ticker, periodo)
        return self._brapi.buscar_historico(ticker, periodo)

    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        if self._e_cripto(ticker):
            return True
        return self._brapi.historico_e_diario(ticker, periodo)

    def _e_cripto(self, ticker: str) -> bool:
        if ticker.startswith("^") or any(caractere.isdigit() for caractere in ticker):
            return False
        return ticker in self._catalogo()

    def _catalogo(self) -> list[str]:
        em_cache = self._cache.obter(_CHAVE_CATALOGO)
        if em_cache is not None:
            return json.loads(em_cache)

        catalogo = self._binance_client.listar_pares_brl()
        self._cache.salvar(_CHAVE_CATALOGO, json.dumps(catalogo), self._ttl_catalogo_segundos)
        return catalogo
