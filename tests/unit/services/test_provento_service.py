from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_operacao import TipoOperacao
from app.domain.value_objects.provento import Provento
from app.integrations.yahoo.client import YahooIndisponivelError
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.provento_service import ProventoService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_fonte_proventos import FakeFonteProventos
from tests.fixtures.fake_mercado_cache import FakeMercadoCache
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository


def _ativo(ticker: str, tipo: TipoAtivo = TipoAtivo.ACAO) -> Ativo:
    return Ativo(uuid4(), ticker, ticker, tipo, None, "BRL", "brapi")


def _cenario():
    ativos = FakeAtivoRepository()
    operacoes = FakeOperacaoRepository()
    fonte = FakeFonteProventos()
    cache = FakeMercadoCache()
    service = ProventoService(ativos, operacoes, fonte, cache, ttl_segundos=86400)
    return service, ativos, operacoes, fonte, cache


def _operar(operacoes, usuario_id, ativo, tipo, quantidade, data):
    operacoes.salvar(
        Operacao(
            uuid4(),
            usuario_id,
            ativo.id,
            tipo,
            Decimal(quantidade),
            Decimal(10),
            data,
            datetime(2026, 1, 1, tzinfo=UTC),
        )
    )


def test_historico_busca_na_fonte_e_guarda_em_cache():
    service, ativos, _, fonte, cache = _cenario()
    ativo = _ativo("PETR4")
    ativos.salvar(ativo)
    fonte.proventos["PETR4"] = [Provento(date(2026, 8, 24), Decimal("0.47156696"))]

    primeira = service.historico(ativo.id)
    segunda = service.historico(ativo.id)

    assert primeira == segunda == [Provento(date(2026, 8, 24), Decimal("0.47156696"))]
    assert fonte.consultas == ["PETR4"]
    assert cache.ttls["proventos:PETR4"] == 86400


def test_historico_de_ativo_inexistente_levanta_erro():
    service, *_ = _cenario()

    with pytest.raises(AtivoNaoEncontradoError):
        service.historico(uuid4())


@pytest.mark.parametrize("tipo", [TipoAtivo.CRIPTO, TipoAtivo.INDICE])
def test_cripto_e_indice_nao_tem_proventos_nem_consultam_a_fonte(tipo):
    service, ativos, _, fonte, _ = _cenario()
    ativo = _ativo("BTC", tipo)
    ativos.salvar(ativo)

    assert service.historico(ativo.id) == []
    assert fonte.consultas == []


def test_ticker_desconhecido_na_fonte_vira_lista_vazia():
    service, ativos, *_ = _cenario()
    ativo = _ativo("XXXX99")
    ativos.salvar(ativo)

    assert service.historico(ativo.id) == []


def test_fonte_indisponivel_propaga():
    service, ativos, _, fonte, _ = _cenario()
    ativo = _ativo("PETR4")
    ativos.salvar(ativo)
    fonte.erro = YahooIndisponivelError()

    with pytest.raises(YahooIndisponivelError):
        service.historico(ativo.id)


def test_recebidos_usa_a_posicao_na_vespera_da_data_ex():
    service, ativos, operacoes, fonte, _ = _cenario()
    usuario_id = uuid4()
    petr = _ativo("PETR4")
    mxrf = _ativo("MXRF11", TipoAtivo.FII)
    ativos.salvar(petr)
    ativos.salvar(mxrf)
    _operar(operacoes, usuario_id, petr, TipoOperacao.COMPRA, "100", date(2026, 1, 10))
    _operar(operacoes, usuario_id, petr, TipoOperacao.VENDA, "40", date(2026, 5, 4))
    _operar(operacoes, usuario_id, petr, TipoOperacao.COMPRA, "10", date(2026, 8, 24))
    _operar(operacoes, usuario_id, mxrf, TipoOperacao.COMPRA, "50", date(2026, 9, 1))
    _operar(operacoes, uuid4(), petr, TipoOperacao.COMPRA, "999", date(2025, 1, 1))
    fonte.proventos["PETR4"] = [
        Provento(date(2025, 12, 1), Decimal("1.00")),
        Provento(date(2026, 3, 2), Decimal("0.50")),
        Provento(date(2026, 8, 24), Decimal("0.20")),
    ]
    fonte.proventos["MXRF11"] = [Provento(date(2026, 9, 30), Decimal("0.10"))]

    resumo = service.recebidos(usuario_id)

    assert [(p.ticker, p.data_ex, p.quantidade, p.total_brl) for p in resumo.proventos] == [
        ("MXRF11", date(2026, 9, 30), Decimal(50), Decimal("5.00")),
        ("PETR4", date(2026, 8, 24), Decimal(60), Decimal("12.00")),
        ("PETR4", date(2026, 3, 2), Decimal(100), Decimal("50.00")),
    ]
    assert resumo.total_brl == Decimal("67.00")


def test_recebidos_sem_operacoes_retorna_zero():
    service, *_ = _cenario()

    resumo = service.recebidos(uuid4())

    assert resumo.total_brl == Decimal(0)
    assert resumo.proventos == []
