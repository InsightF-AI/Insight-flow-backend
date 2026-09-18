from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.operacao import Operacao
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.domain.enums.tipo_operacao import TipoOperacao
from app.domain.value_objects.comparativo import Comparativo
from app.domain.value_objects.distribuicao import Distribuicao
from app.domain.value_objects.posicao import Posicao
from app.domain.value_objects.rentabilidade import Rentabilidade
from app.integrations.bcb.client import BcbClient, BcbIndisponivelError
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.services.cambio_service import CambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
    PortfolioVazioError,
    QuantidadeInsuficienteError,
)

logger = logging.getLogger(__name__)


@dataclass
class EstadoPosicao:
    quantidade: Decimal = Decimal(0)
    preco_medio: Decimal = Decimal(0)
    lucro_realizado: Decimal = Decimal(0)


def replay_operacoes(operacoes: list[Operacao]) -> EstadoPosicao:
    estado = EstadoPosicao()
    for op in sorted(operacoes, key=lambda o: (o.data, o.criado_em)):
        if op.tipo == TipoOperacao.COMPRA:
            custo_total = estado.quantidade * estado.preco_medio + op.valor_total()
            estado.quantidade += op.quantidade
            estado.preco_medio = custo_total / estado.quantidade
        else:
            if op.quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(op.ativo_id)
            estado.lucro_realizado += (op.preco_unitario - estado.preco_medio) * op.quantidade
            estado.quantidade -= op.quantidade
            if estado.quantidade == 0:
                estado.preco_medio = Decimal(0)
    return estado


class PortfolioService:
    def __init__(
        self,
        operacao_repository: OperacaoRepository,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
        cambio_service: CambioService,
        bcb_client: BcbClient,
    ):
        self._operacao_repository = operacao_repository
        self._ativo_repository = ativo_repository
        self._dados_mercado_service = dados_mercado_service
        self._cambio_service = cambio_service
        self._bcb_client = bcb_client

    def registrar_operacao(
        self,
        usuario_id: UUID,
        ativo_id: UUID,
        tipo: TipoOperacao,
        quantidade: Decimal,
        preco_unitario: Decimal,
        data: date,
    ) -> Operacao:
        if quantidade <= 0:
            raise OperacaoInvalidaError("quantidade deve ser maior que zero")
        if preco_unitario <= 0:
            raise OperacaoInvalidaError("preco_unitario deve ser maior que zero")
        if data > datetime.now(UTC).date():
            raise OperacaoInvalidaError("data nao pode ser futura")

        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)

        operacao = Operacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            tipo=tipo,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
            data=data,
            criado_em=datetime.now(UTC),
        )

        if tipo == TipoOperacao.VENDA:
            operacoes_existentes = [
                op
                for op in self._operacao_repository.listar_por_usuario(usuario_id)
                if op.ativo_id == ativo_id
            ]
            replay_operacoes([*operacoes_existentes, operacao])

        self._operacao_repository.salvar(operacao)
        return operacao

    def listar_operacoes(self, usuario_id: UUID) -> list[Operacao]:
        return self._operacao_repository.listar_por_usuario(usuario_id)

    def remover_operacao(self, usuario_id: UUID, operacao_id: UUID) -> None:
        operacao = self._buscar_operacao(usuario_id, operacao_id)
        operacoes_restantes = [
            op
            for op in self._operacao_repository.listar_por_usuario(usuario_id)
            if op.ativo_id == operacao.ativo_id and op.id != operacao.id
        ]
        replay_operacoes(operacoes_restantes)
        self._operacao_repository.remover(operacao)

    def posicoes(self, usuario_id: UUID) -> list[Posicao]:
        estados = self._replay_por_ativo(usuario_id)
        resultado: list[Posicao] = []
        for ativo_id, estado in estados.items():
            if estado.quantidade == 0:
                continue
            ativo = self._ativo_repository.buscar_por_id(ativo_id)
            try:
                cotacao = self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)
            except (BrapiIndisponivelError, TickerNaoEncontradoError):
                logger.warning(
                    "Cotacao indisponivel para %s; ativo omitido das posicoes.", ativo.ticker
                )
                continue

            valor_mercado = estado.quantidade * cotacao.preco
            valor_mercado_brl = self._cambio_service.converter(
                valor_mercado, de=ativo.moeda, para="BRL"
            )
            resultado.append(
                Posicao(
                    ativo_id=ativo_id,
                    ticker=ativo.ticker,
                    quantidade=estado.quantidade,
                    preco_medio=estado.preco_medio,
                    cotacao_atual=cotacao.preco,
                    valor_mercado=valor_mercado,
                    valor_mercado_brl=valor_mercado_brl,
                    lucro_nao_realizado=valor_mercado - (estado.quantidade * estado.preco_medio),
                    lucro_realizado=estado.lucro_realizado,
                )
            )
        return resultado

    def rentabilidade(self, usuario_id: UUID) -> Rentabilidade:
        estados = self._replay_por_ativo(usuario_id)
        custo_base_brl = Decimal(0)
        valor_mercado_brl = Decimal(0)
        lucro_realizado_brl = Decimal(0)

        for ativo_id, estado in estados.items():
            ativo = self._ativo_repository.buscar_por_id(ativo_id)
            lucro_realizado_brl += self._cambio_service.converter(
                estado.lucro_realizado, de=ativo.moeda, para="BRL"
            )
            if estado.quantidade == 0:
                continue

            custo_base = estado.quantidade * estado.preco_medio
            custo_base_brl += self._cambio_service.converter(custo_base, de=ativo.moeda, para="BRL")
            try:
                cotacao = self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)
            except (BrapiIndisponivelError, TickerNaoEncontradoError):
                logger.warning(
                    "Cotacao indisponivel para %s; excluido da rentabilidade.", ativo.ticker
                )
                continue
            valor_mercado = estado.quantidade * cotacao.preco
            valor_mercado_brl += self._cambio_service.converter(
                valor_mercado, de=ativo.moeda, para="BRL"
            )

        lucro_nao_realizado_brl = valor_mercado_brl - custo_base_brl
        percentual = (
            lucro_nao_realizado_brl / custo_base_brl if custo_base_brl != 0 else Decimal(0)
        )
        return Rentabilidade(
            custo_base_brl=custo_base_brl,
            valor_mercado_brl=valor_mercado_brl,
            lucro_nao_realizado_brl=lucro_nao_realizado_brl,
            lucro_realizado_brl=lucro_realizado_brl,
            percentual=percentual,
        )

    def distribuicao(self, usuario_id: UUID) -> Distribuicao:
        posicoes = self.posicoes(usuario_id)
        total_brl = sum((p.valor_mercado_brl for p in posicoes), Decimal(0))

        por_classe: dict[TipoAtivo, Decimal] = {}
        por_setor: dict[str, Decimal] = {}
        por_moeda: dict[str, Decimal] = {}

        for posicao in posicoes:
            ativo = self._ativo_repository.buscar_por_id(posicao.ativo_id)
            fracao = posicao.valor_mercado_brl / total_brl if total_brl != 0 else Decimal(0)
            por_classe[ativo.tipo] = por_classe.get(ativo.tipo, Decimal(0)) + fracao
            setor = ativo.setor if ativo.setor is not None else "N/A"
            por_setor[setor] = por_setor.get(setor, Decimal(0)) + fracao
            por_moeda[ativo.moeda] = por_moeda.get(ativo.moeda, Decimal(0)) + fracao

        return Distribuicao(por_classe=por_classe, por_setor=por_setor, por_moeda=por_moeda)

    def comparativo_benchmark(self, usuario_id: UUID, benchmark: TipoBenchmark) -> Comparativo:
        operacoes = self._operacao_repository.listar_por_usuario(usuario_id)
        if not operacoes:
            raise PortfolioVazioError(usuario_id)

        data_inicio = min(op.data for op in operacoes)
        rentabilidade_carteira = self.rentabilidade(usuario_id).percentual

        if benchmark == TipoBenchmark.CDI:
            rentabilidade_benchmark = self._rentabilidade_cdi(data_inicio)
        else:
            rentabilidade_benchmark = self._rentabilidade_ibovespa(data_inicio)

        return Comparativo(
            benchmark=benchmark,
            rentabilidade_carteira_percentual=rentabilidade_carteira,
            rentabilidade_benchmark_percentual=rentabilidade_benchmark,
        )

    def _rentabilidade_cdi(self, data_inicio: date) -> Decimal | None:
        try:
            pontos = self._bcb_client.buscar_serie_cdi(data_inicio, datetime.now(UTC).date())
        except BcbIndisponivelError:
            logger.warning("CDI indisponivel; comparativo de benchmark sem CDI.")
            return None

        if not pontos:
            return None

        fator = Decimal(1)
        for ponto in pontos:
            fator *= Decimal(1) + ponto.valor / Decimal(100)
        return fator - Decimal(1)

    def _rentabilidade_ibovespa(self, data_inicio: date) -> Decimal | None:
        periodo = _periodo_desde(data_inicio)
        try:
            pontos = self._dados_mercado_service.buscar_historico("^BVSP", periodo)
        except (BrapiIndisponivelError, TickerNaoEncontradoError):
            logger.warning("Ibovespa indisponivel; comparativo de benchmark sem Ibovespa.")
            return None
        if not pontos:
            return None
        return (pontos[-1].fechamento - pontos[0].fechamento) / pontos[0].fechamento

    def _replay_por_ativo(self, usuario_id: UUID) -> dict[UUID, EstadoPosicao]:
        operacoes_por_ativo: dict[UUID, list[Operacao]] = {}
        for operacao in self._operacao_repository.listar_por_usuario(usuario_id):
            operacoes_por_ativo.setdefault(operacao.ativo_id, []).append(operacao)
        estados: dict[UUID, EstadoPosicao] = {}
        for ativo_id, operacoes in operacoes_por_ativo.items():
            try:
                estados[ativo_id] = replay_operacoes(operacoes)
            except QuantidadeInsuficienteError:
                logger.warning(
                    "Sequencia de operacoes inconsistente para o ativo %s; ativo omitido.",
                    ativo_id,
                )
        return estados

    def _buscar_operacao(self, usuario_id: UUID, operacao_id: UUID) -> Operacao:
        operacao = self._operacao_repository.buscar_por_id(operacao_id)
        if operacao is None or operacao.usuario_id != usuario_id:
            raise OperacaoNaoEncontradaError(operacao_id)
        return operacao


def _periodo_desde(data_inicio: date) -> PeriodoHistorico:
    dias = (datetime.now(UTC).date() - data_inicio).days
    if dias <= 1:
        return PeriodoHistorico.UM_DIA
    if dias <= 7:
        return PeriodoHistorico.UMA_SEMANA
    if dias <= 30:
        return PeriodoHistorico.UM_MES
    if dias <= 90:
        return PeriodoHistorico.TRES_MESES
    if dias <= 365:
        return PeriodoHistorico.UM_ANO
    return PeriodoHistorico.CINCO_ANOS
