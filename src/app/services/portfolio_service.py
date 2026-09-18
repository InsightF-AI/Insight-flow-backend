from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.integrations.bcb.client import BcbClient
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.services.cambio_service import CambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
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
        if data > date.today():
            raise OperacaoInvalidaError("data nao pode ser futura")

        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)

        if tipo == TipoOperacao.VENDA:
            operacoes_existentes = [
                op
                for op in self._operacao_repository.listar_por_usuario(usuario_id)
                if op.ativo_id == ativo_id
            ]
            estado = replay_operacoes(operacoes_existentes)
            if quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(ativo_id)

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
        self._operacao_repository.salvar(operacao)
        return operacao

    def listar_operacoes(self, usuario_id: UUID) -> list[Operacao]:
        return self._operacao_repository.listar_por_usuario(usuario_id)

    def remover_operacao(self, usuario_id: UUID, operacao_id: UUID) -> None:
        operacao = self._buscar_operacao(usuario_id, operacao_id)
        self._operacao_repository.remover(operacao)

    def _buscar_operacao(self, usuario_id: UUID, operacao_id: UUID) -> Operacao:
        operacao = self._operacao_repository.buscar_por_id(operacao_id)
        if operacao is None or operacao.usuario_id != usuario_id:
            raise OperacaoNaoEncontradaError(operacao_id)
        return operacao
