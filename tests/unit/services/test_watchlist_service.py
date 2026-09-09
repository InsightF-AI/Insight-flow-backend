from uuid import uuid4

import pytest

from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.exceptions import AtivoJaNaWatchlistError, ItemWatchlistNaoEncontradoError
from app.services.watchlist_service import WatchlistService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_watchlist_repository import FakeWatchlistRepository


def _service() -> WatchlistService:
    return WatchlistService(FakeWatchlistRepository(), FakeAtivoRepository())


def test_adicionar_cria_o_ativo_e_o_item_na_watchlist():
    service = _service()
    usuario_id = uuid4()

    item = service.adicionar(
        usuario_id=usuario_id,
        ticker="PETR4",
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        moeda="BRL",
    )

    assert item.ativo.ticker == "PETR4"
    assert item.watchlist.usuario_id == usuario_id
    assert item.watchlist.notificar is True


def test_adicionar_reaproveita_ativo_existente_com_mesmo_ticker():
    service = _service()
    primeiro = service.adicionar(
        usuario_id=uuid4(), ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    segundo = service.adicionar(
        usuario_id=uuid4(), ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    assert segundo.ativo.id == primeiro.ativo.id


def test_adicionar_ativo_ja_presente_na_watchlist_do_usuario_lanca_erro():
    service = _service()
    usuario_id = uuid4()
    service.adicionar(
        usuario_id=usuario_id, ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    with pytest.raises(AtivoJaNaWatchlistError):
        service.adicionar(
            usuario_id=usuario_id,
            ticker="PETR4",
            nome="Petrobras PN",
            tipo=TipoAtivo.ACAO,
            moeda="BRL",
        )


def test_listar_retorna_os_itens_do_usuario():
    service = _service()
    usuario_id = uuid4()
    service.adicionar(
        usuario_id=usuario_id, ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )
    service.adicionar(
        usuario_id=uuid4(), ticker="VALE3", nome="Vale ON", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    itens = service.listar(usuario_id)

    assert len(itens) == 1
    assert itens[0].ativo.ticker == "PETR4"


def test_remover_apaga_o_item_da_watchlist():
    service = _service()
    usuario_id = uuid4()
    item = service.adicionar(
        usuario_id=usuario_id, ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    service.remover(usuario_id, item.ativo.id)

    assert service.listar(usuario_id) == []


def test_remover_item_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(ItemWatchlistNaoEncontradoError):
        service.remover(uuid4(), uuid4())


def test_definir_notificacao_desabilita_para_o_item():
    service = _service()
    usuario_id = uuid4()
    item = service.adicionar(
        usuario_id=usuario_id, ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL"
    )

    atualizado = service.definir_notificacao(usuario_id, item.ativo.id, notificar=False)

    assert atualizado.watchlist.notificar is False


def test_definir_notificacao_em_item_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(ItemWatchlistNaoEncontradoError):
        service.definir_notificacao(uuid4(), uuid4(), notificar=False)
