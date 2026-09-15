from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.integrations.bcb.client import BcbIndisponivelError
from app.integrations.brapi.client import AtivoEncontrado
from app.services.alerta_service import AlertaService
from app.services.exceptions import AlertaNaoEncontradoError, AtivoNaoEncontradoError
from tests.fixtures.fake_alerta_repository import FakeAlertaRepository
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService

_PETR4 = AtivoEncontrado(
    ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo e Gas"
)


def _service(catalogo: list[AtivoEncontrado] | None = None) -> AlertaService:
    return AlertaService(
        FakeAlertaRepository(),
        FakeAtivoRepository(),
        FakeDadosMercadoService(catalogo),
        FakeCambioService(),
    )


def test_criar_alerta_resolve_o_ativo_na_brapi_e_persiste():
    service = _service([_PETR4])
    usuario_id = uuid4()

    item = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    assert item.alerta.usuario_id == usuario_id
    assert item.alerta.tipo_condicao == TipoCondicaoAlerta.PRECO_MAIOR_IGUAL
    assert item.alerta.valor_alvo == Decimal("40.00")
    assert item.alerta.moeda_alvo == "BRL"
    assert item.alerta.ativo is True
    assert item.ativo.ticker == "PETR4"


def test_criar_alerta_ticker_nao_encontrado_lanca_erro():
    service = _service([])

    with pytest.raises(AtivoNaoEncontradoError):
        service.criar_alerta(
            usuario_id=uuid4(),
            ticker="NAOEXISTE",
            tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
            valor_alvo=Decimal("40.00"),
        )


def test_criar_alerta_valor_alvo_invalido_propaga_erro_da_entidade():
    service = _service([_PETR4])

    with pytest.raises(ValueError):
        service.criar_alerta(
            usuario_id=uuid4(),
            ticker="PETR4",
            tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
            valor_alvo=Decimal(0),
        )


def test_listar_alertas_retorna_apenas_os_do_usuario():
    service = _service([_PETR4])
    usuario_id = uuid4()
    service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )
    service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("50.00"),
    )

    itens = service.listar_alertas(usuario_id)

    assert len(itens) == 1
    assert itens[0].alerta.usuario_id == usuario_id
    assert itens[0].ativo.ticker == "PETR4"


def test_atualizar_alerta_altera_valor_alvo():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    atualizado = service.atualizar_alerta(usuario_id, item.alerta.id, valor_alvo=Decimal("45.00"))

    assert atualizado.alerta.valor_alvo == Decimal("45.00")


def test_atualizar_alerta_valor_alvo_invalido_lanca_erro():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    with pytest.raises(ValueError):
        service.atualizar_alerta(usuario_id, item.alerta.id, valor_alvo=Decimal(0))


def test_atualizar_alerta_reativar_rearma_o_estado():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )
    item.alerta.avaliar(Decimal("40.00"), datetime.now(UTC))
    service.atualizar_alerta(usuario_id, item.alerta.id, ativo=False)

    reativado = service.atualizar_alerta(usuario_id, item.alerta.id, ativo=True)

    assert reativado.alerta.ultimo_estado is False


def test_atualizar_alerta_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AlertaNaoEncontradoError):
        service.atualizar_alerta(uuid4(), uuid4(), valor_alvo=Decimal("10.00"))


def test_atualizar_alerta_de_outro_usuario_lanca_erro():
    service = _service([_PETR4])
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    with pytest.raises(AlertaNaoEncontradoError):
        service.atualizar_alerta(uuid4(), item.alerta.id, valor_alvo=Decimal("45.00"))


def test_remover_alerta_apaga_o_alerta():
    service = _service([_PETR4])
    usuario_id = uuid4()
    item = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    service.remover_alerta(usuario_id, item.alerta.id)

    assert service.listar_alertas(usuario_id) == []


def test_remover_alerta_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AlertaNaoEncontradoError):
        service.remover_alerta(uuid4(), uuid4())


def test_avaliar_alertas_dispara_quando_preco_atinge_a_condicao():
    service = _service([_PETR4])
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    disparados = service.avaliar_alertas(item.ativo.id, Decimal("40.00"))

    assert len(disparados) == 1
    assert disparados[0].id == item.alerta.id


def test_avaliar_alertas_nao_dispara_novamente_enquanto_condicao_permanece():
    service = _service([_PETR4])
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )
    service.avaliar_alertas(item.ativo.id, Decimal("40.00"))

    disparados = service.avaliar_alertas(item.ativo.id, Decimal("41.00"))

    assert disparados == []


def test_avaliar_alertas_rearma_quando_condicao_deixa_de_ser_atendida():
    service = _service([_PETR4])
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )
    service.avaliar_alertas(item.ativo.id, Decimal("40.00"))
    service.avaliar_alertas(item.ativo.id, Decimal("39.00"))

    disparados = service.avaliar_alertas(item.ativo.id, Decimal("40.50"))

    assert len(disparados) == 1


def test_avaliar_alertas_ignora_alerta_inativo():
    service = _service([_PETR4])
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )
    item.alerta.ativo = False

    disparados = service.avaliar_alertas(item.ativo.id, Decimal("40.00"))

    assert disparados == []


def test_avaliar_alertas_converte_preco_quando_moeda_alvo_difere_do_ativo():
    cambio_service = FakeCambioService(taxa=Decimal("5.00"))
    service = AlertaService(
        FakeAlertaRepository(),
        FakeAtivoRepository(),
        FakeDadosMercadoService([_PETR4]),
        cambio_service,
    )
    item = service.criar_alerta(
        usuario_id=uuid4(),
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("200.00"),
    )
    item.alerta.moeda_alvo = "USD"

    disparados = service.avaliar_alertas(item.ativo.id, Decimal("40.00"))

    assert len(disparados) == 1
    assert cambio_service.chamadas == 1


def test_avaliar_alertas_pula_alerta_quando_cambio_indisponivel_e_continua_o_lote():
    cambio_service = FakeCambioService(indisponivel=True)
    service = AlertaService(
        FakeAlertaRepository(),
        FakeAtivoRepository(),
        FakeDadosMercadoService([_PETR4]),
        cambio_service,
    )
    usuario_id = uuid4()
    item_com_conversao = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("200.00"),
    )
    item_com_conversao.alerta.moeda_alvo = "USD"
    item_sem_conversao = service.criar_alerta(
        usuario_id=usuario_id,
        ticker="PETR4",
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
    )

    disparados = service.avaliar_alertas(item_com_conversao.ativo.id, Decimal("40.00"))

    assert len(disparados) == 1
    assert disparados[0].id == item_sem_conversao.alerta.id
