from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado, BrapiIndisponivelError, PontoHistorico
from app.services.ativo_service import AtivoService
from app.services.exceptions import (
    AtivoJaNaWatchlistError,
    AtivoNaoEncontradoError,
    ItemWatchlistNaoEncontradoError,
)
from app.services.watchlist_service import WatchlistService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_watchlist_repository import FakeWatchlistRepository

_PETR4 = AtivoEncontrado(
    ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo e Gas"
)


_PONTO_PETR4 = PontoHistorico(
    data=datetime(2026, 9, 1, tzinfo=UTC),
    abertura=Decimal("36.00"),
    maxima=Decimal("37.00"),
    minima=Decimal("35.50"),
    fechamento=Decimal("36.50"),
    volume=Decimal(1000),
)


def _service(
    catalogo: list[AtivoEncontrado] | None = None,
    dados_mercado_service: FakeDadosMercadoService | None = None,
    cotacao_repository: FakeCotacaoRepository | None = None,
) -> WatchlistService:
    ativo_repository = FakeAtivoRepository()
    dados_mercado_service = dados_mercado_service or FakeDadosMercadoService(catalogo)
    return WatchlistService(
        FakeWatchlistRepository(),
        ativo_repository,
        dados_mercado_service,
        AtivoService(
            ativo_repository, dados_mercado_service, cotacao_repository or FakeCotacaoRepository()
        ),
        periodo_backfill=PeriodoHistorico.TRES_MESES,
        minimo_cotacoes=50,
    )


def test_adicionar_busca_o_ativo_na_brapi_e_cria_o_item_na_watchlist():
    service = _service([_PETR4])
    usuario_id = uuid4()

    item = service.adicionar(usuario_id=usuario_id, ticker="PETR4")

    assert item.ativo.ticker == "PETR4"
    assert item.ativo.nome == "Petrobras PN"
    assert item.ativo.tipo is TipoAtivo.ACAO
    assert item.ativo.fonte_dados == "brapi"
    assert item.watchlist.usuario_id == usuario_id
    assert item.watchlist.notificar is True


def test_adicionar_ticker_nao_encontrado_na_brapi_lanca_erro():
    service = _service([])

    with pytest.raises(AtivoNaoEncontradoError):
        service.adicionar(usuario_id=uuid4(), ticker="NAOEXISTE")


def test_adicionar_normaliza_ticker_minusculo_para_maiusculo():
    service = _service([_PETR4])
    usuario_id = uuid4()

    item = service.adicionar(usuario_id=usuario_id, ticker="petr4")

    assert item.ativo.ticker == "PETR4"


def test_adicionar_reaproveita_ativo_ja_persistido_com_ticker_em_outra_caixa():
    service = _service([_PETR4])
    primeiro = service.adicionar(usuario_id=uuid4(), ticker="PETR4")

    segundo = service.adicionar(usuario_id=uuid4(), ticker="petr4")

    assert segundo.ativo.id == primeiro.ativo.id


def test_adicionar_com_brapi_indisponivel_propaga_o_erro():
    service = _service(dados_mercado_service=FakeDadosMercadoService(indisponivel=True))

    with pytest.raises(BrapiIndisponivelError):
        service.adicionar(usuario_id=uuid4(), ticker="PETR4")


def test_adicionar_reaproveita_ativo_ja_persistido_com_mesmo_ticker():
    service = _service([_PETR4])
    primeiro = service.adicionar(usuario_id=uuid4(), ticker="PETR4")

    segundo = service.adicionar(usuario_id=uuid4(), ticker="PETR4")

    assert segundo.ativo.id == primeiro.ativo.id


def test_adicionar_ativo_ja_presente_na_watchlist_do_usuario_lanca_erro():
    service = _service([_PETR4])
    usuario_id = uuid4()
    service.adicionar(usuario_id=usuario_id, ticker="PETR4")

    with pytest.raises(AtivoJaNaWatchlistError):
        service.adicionar(usuario_id=usuario_id, ticker="PETR4")


def test_listar_retorna_os_itens_do_usuario():
    service = _service(
        [
            _PETR4,
            AtivoEncontrado(
                ticker="VALE3", nome="Vale ON", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Mineracao"
            ),
        ]
    )
    usuario_id = uuid4()
    service.adicionar(usuario_id=usuario_id, ticker="PETR4")
    service.adicionar(usuario_id=uuid4(), ticker="VALE3")

    itens = service.listar(usuario_id)

    assert len(itens) == 1
    assert itens[0].ativo.ticker == "PETR4"


def test_remover_apaga_o_item_da_watchlist():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.adicionar(usuario_id=usuario_id, ticker="PETR4")

    service.remover(usuario_id, item.ativo.id)

    assert service.listar(usuario_id) == []


def test_remover_item_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(ItemWatchlistNaoEncontradoError):
        service.remover(uuid4(), uuid4())


def test_definir_notificacao_desabilita_para_o_item():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.adicionar(usuario_id=usuario_id, ticker="PETR4")

    atualizado = service.definir_notificacao(usuario_id, item.ativo.id, notificar=False)

    assert atualizado.watchlist.notificar is False


def test_definir_notificacao_em_item_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(ItemWatchlistNaoEncontradoError):
        service.definir_notificacao(uuid4(), uuid4(), notificar=False)


def test_adicionar_coleta_o_historico_de_backfill_do_ativo():
    dados_mercado_service = FakeDadosMercadoService([_PETR4], historicos={"PETR4": [_PONTO_PETR4]})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(
        dados_mercado_service=dados_mercado_service, cotacao_repository=cotacao_repository
    )

    item = service.adicionar(usuario_id=uuid4(), ticker="PETR4")

    assert dados_mercado_service.historicos_solicitados == [("PETR4", PeriodoHistorico.TRES_MESES)]
    assert len(cotacao_repository.listar_por_ativo(item.ativo.id)) == 1


def test_adicionar_mantem_o_item_quando_a_coleta_de_historico_falha():
    service = _service([_PETR4])
    usuario_id = uuid4()

    item = service.adicionar(usuario_id=usuario_id, ticker="PETR4")

    assert [i.ativo.id for i in service.listar(usuario_id)] == [item.ativo.id]
