from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.domain.enums.tipo_operacao import TipoOperacao
from app.domain.value_objects.comparativo import Comparativo
from app.domain.value_objects.distribuicao import Distribuicao
from app.domain.value_objects.posicao import Posicao
from app.domain.value_objects.rentabilidade import Rentabilidade


class RegistrarOperacaoRequest(BaseModel):
    ativo_id: UUID
    tipo: TipoOperacao
    quantidade: Decimal = Field(gt=0)
    preco_unitario: Decimal = Field(gt=0)
    data: date


class OperacaoResponse(BaseModel):
    id: UUID
    ativo_id: UUID
    tipo: TipoOperacao
    quantidade: Decimal
    preco_unitario: Decimal
    data: date
    criado_em: datetime

    @staticmethod
    def de(operacao: Operacao) -> "OperacaoResponse":
        return OperacaoResponse(
            id=operacao.id,
            ativo_id=operacao.ativo_id,
            tipo=operacao.tipo,
            quantidade=operacao.quantidade,
            preco_unitario=operacao.preco_unitario,
            data=operacao.data,
            criado_em=operacao.criado_em,
        )


class PosicaoResponse(BaseModel):
    ativo_id: UUID
    ticker: str
    quantidade: Decimal
    preco_medio: Decimal
    cotacao_atual: Decimal
    valor_mercado: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado: Decimal
    lucro_realizado: Decimal

    @staticmethod
    def de(posicao: Posicao) -> "PosicaoResponse":
        return PosicaoResponse(
            ativo_id=posicao.ativo_id,
            ticker=posicao.ticker,
            quantidade=posicao.quantidade,
            preco_medio=posicao.preco_medio,
            cotacao_atual=posicao.cotacao_atual,
            valor_mercado=posicao.valor_mercado,
            valor_mercado_brl=posicao.valor_mercado_brl,
            lucro_nao_realizado=posicao.lucro_nao_realizado,
            lucro_realizado=posicao.lucro_realizado,
        )


class RentabilidadeResponse(BaseModel):
    custo_base_brl: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado_brl: Decimal
    lucro_realizado_brl: Decimal
    percentual: Decimal

    @staticmethod
    def de(rentabilidade: Rentabilidade) -> "RentabilidadeResponse":
        return RentabilidadeResponse(
            custo_base_brl=rentabilidade.custo_base_brl,
            valor_mercado_brl=rentabilidade.valor_mercado_brl,
            lucro_nao_realizado_brl=rentabilidade.lucro_nao_realizado_brl,
            lucro_realizado_brl=rentabilidade.lucro_realizado_brl,
            percentual=rentabilidade.percentual,
        )


class ComparativoResponse(BaseModel):
    benchmark: TipoBenchmark
    rentabilidade_carteira_percentual: Decimal
    rentabilidade_benchmark_percentual: Decimal | None

    @staticmethod
    def de(comparativo: Comparativo) -> "ComparativoResponse":
        return ComparativoResponse(
            benchmark=comparativo.benchmark,
            rentabilidade_carteira_percentual=comparativo.rentabilidade_carteira_percentual,
            rentabilidade_benchmark_percentual=comparativo.rentabilidade_benchmark_percentual,
        )


class DistribuicaoResponse(BaseModel):
    por_classe: dict[TipoAtivo, Decimal]
    por_setor: dict[str, Decimal]
    por_moeda: dict[str, Decimal]

    @staticmethod
    def de(distribuicao: Distribuicao) -> "DistribuicaoResponse":
        return DistribuicaoResponse(
            por_classe=distribuicao.por_classe,
            por_setor=distribuicao.por_setor,
            por_moeda=distribuicao.por_moeda,
        )
