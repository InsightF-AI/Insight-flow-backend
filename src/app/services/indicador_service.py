from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pandas as pd
import pandas_ta as ta

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository
from app.services.exceptions import AtivoNaoEncontradoError


class IndicadorService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        cotacao_repository: CotacaoRepository,
        indicador_repository: IndicadorTecnicoRepository,
    ):
        self._ativo_repository = ativo_repository
        self._cotacao_repository = cotacao_repository
        self._indicador_repository = indicador_repository

    def calcular_sma(self, cotacoes: list[Cotacao], periodo: int) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.sma(fechamentos, length=periodo)
        if resultado is None or pd.isna(resultado.iloc[-1]):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.SMA,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(resultado.iloc[-1])),
            valores_auxiliares=None,
        )

    def calcular_rsi(self, cotacoes: list[Cotacao], periodo: int = 14) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.rsi(fechamentos, length=periodo)
        if resultado is None or pd.isna(resultado.iloc[-1]):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.RSI,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(resultado.iloc[-1])),
            valores_auxiliares=None,
        )

    def calcular_macd(
        self, cotacoes: list[Cotacao], rapida: int = 12, lenta: int = 26, sinal: int = 9
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.macd(fechamentos, fast=rapida, slow=lenta, signal=sinal)
        if resultado is None:
            return None
        linha_macd = resultado.iloc[-1, 0]
        linha_histograma = resultado.iloc[-1, 1]
        linha_sinal = resultado.iloc[-1, 2]
        if pd.isna(linha_macd) or pd.isna(linha_histograma) or pd.isna(linha_sinal):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.MACD,
            parametros={"rapida": rapida, "lenta": lenta, "sinal": sinal},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(linha_macd)),
            valores_auxiliares={
                "linha_sinal": float(linha_sinal),
                "histograma": float(linha_histograma),
            },
        )

    def calcular_bollinger(
        self, cotacoes: list[Cotacao], periodo: int = 20, desvios: float = 2
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.bbands(fechamentos, length=periodo, std=desvios)
        if resultado is None:
            return None
        banda_inferior = resultado.iloc[-1, 0]
        banda_media = resultado.iloc[-1, 1]
        banda_superior = resultado.iloc[-1, 2]
        if pd.isna(banda_inferior) or pd.isna(banda_media) or pd.isna(banda_superior):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.BOLLINGER,
            parametros={"periodo": periodo, "desvios": desvios},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(banda_media)),
            valores_auxiliares={
                "banda_superior": float(banda_superior),
                "banda_inferior": float(banda_inferior),
            },
        )

    def calcular_volume_relativo(
        self, cotacoes: list[Cotacao], periodo: int = 20
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        volumes = pd.Series([float(c.volume) for c in cotacoes])
        media = ta.sma(volumes, length=periodo)
        if media is None or pd.isna(media.iloc[-1]) or media.iloc[-1] == 0:
            return None
        razao = volumes.iloc[-1] / media.iloc[-1]
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.VOLUME_RELATIVO,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(razao)),
            valores_auxiliares=None,
        )

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
