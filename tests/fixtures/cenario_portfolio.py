from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_operacao import TipoOperacao
from app.integrations.brapi.client import CotacaoAtual
from app.services.portfolio_service import PortfolioService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository

ATIVO_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)

ATIVO_VALE3 = Ativo(
    id=uuid4(),
    ticker="VALE3",
    nome="Vale ON",
    tipo=TipoAtivo.ACAO,
    setor="Mineracao",
    moeda="BRL",
    fonte_dados="manual",
)


class _BcbClientSemDados:
    def buscar_serie_cdi(self, data_inicio, data_fim):
        return []


def cotacao_atual(ticker: str, preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker=ticker,
        preco=Decimal(preco),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal(1000),
    )


def nova_operacao(
    usuario_id: UUID,
    ativo_id: UUID,
    tipo: TipoOperacao = TipoOperacao.COMPRA,
    quantidade: str = "10",
    preco: str = "30.00",
    dia: int = 1,
) -> Operacao:
    return Operacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo=tipo,
        quantidade=Decimal(quantidade),
        preco_unitario=Decimal(preco),
        data=date(2026, 9, dia),
        criado_em=datetime(2026, 9, dia, 10, 0, 0, tzinfo=UTC),
    )


def montar_portfolio_service(
    ativos: list[Ativo],
    operacoes: list[Operacao],
    cotacoes: dict[str, CotacaoAtual],
    ativo_repository: FakeAtivoRepository | None = None,
) -> PortfolioService:
    ativo_repository = ativo_repository if ativo_repository is not None else FakeAtivoRepository()
    for ativo in ativos:
        ativo_repository.salvar(ativo)
    operacao_repository = FakeOperacaoRepository()
    for operacao in operacoes:
        operacao_repository.salvar(operacao)
    return PortfolioService(
        operacao_repository,
        ativo_repository,
        FakeDadosMercadoService(cotacoes=cotacoes),
        FakeCambioService(taxa=Decimal(1)),
        _BcbClientSemDados(),
    )
