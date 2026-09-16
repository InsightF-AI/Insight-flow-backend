from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.ativo import Ativo
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.integrations.brapi.client import CotacaoAtual
from app.services.exceptions import NotificacaoNaoEncontradaError
from app.services.notificacao_service import NotificacaoService
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository

_ATIVO = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def _service() -> NotificacaoService:
    return NotificacaoService(FakeNotificacaoRepository())


def _sinal(regra_id=None) -> Sinal:
    return Sinal(
        id=uuid4(),
        ativo_id=_ATIVO.id,
        regra_id=regra_id if regra_id is not None else REGRAS_PADRAO[0].id,
        data_ativacao=datetime(2026, 9, 16, 10, 0, 0, tzinfo=UTC),
        contexto={"valor": "28.4"},
    )


def test_enviar_alerta_persiste_notificacao_de_sinal_ativado():
    service = _service()
    regra = REGRAS_PADRAO[0]

    notificacao = service.enviar_alerta(uuid4(), _sinal(regra.id), _ATIVO)

    assert notificacao.tipo == TipoNotificacao.SINAL_ATIVADO
    assert notificacao.ativo_id == _ATIVO.id
    assert regra.nome in notificacao.mensagem
    assert notificacao.lida is False


def test_enviar_alerta_com_regra_inexistente_usa_mensagem_generica():
    service = _service()

    notificacao = service.enviar_alerta(uuid4(), _sinal(uuid4()), _ATIVO)

    assert "sinal tecnico" in notificacao.mensagem


def test_enviar_alerta_personalizado_persiste_notificacao_de_alerta_disparado():
    service = _service()
    alerta = AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=_ATIVO.id,
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
        moeda_alvo="BRL",
        criado_em=datetime(2026, 9, 16, 10, 0, 0, tzinfo=UTC),
    )
    cotacao = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("40.50"),
        variacao=Decimal("0.5"),
        variacao_percentual=Decimal("1.25"),
        maxima_dia=Decimal("41.00"),
        minima_dia=Decimal("39.50"),
        volume=Decimal("1000000"),
    )

    notificacao = service.enviar_alerta_personalizado(alerta.usuario_id, alerta, cotacao)

    assert notificacao.tipo == TipoNotificacao.ALERTA_DISPARADO
    assert notificacao.ativo_id == _ATIVO.id
    assert "PETR4" in notificacao.mensagem
    assert "40.00" in notificacao.mensagem


def test_listar_notificacoes_retorna_apenas_as_do_usuario():
    service = _service()
    usuario_id = uuid4()
    service.enviar_alerta(usuario_id, _sinal(), _ATIVO)
    service.enviar_alerta(uuid4(), _sinal(), _ATIVO)

    notificacoes = service.listar_notificacoes(usuario_id)

    assert len(notificacoes) == 1
    assert notificacoes[0].usuario_id == usuario_id


def test_listar_notificacoes_com_apenas_nao_lidas_filtra_as_lidas():
    service = _service()
    usuario_id = uuid4()
    lida = service.enviar_alerta(usuario_id, _sinal(), _ATIVO)
    service.enviar_alerta(usuario_id, _sinal(), _ATIVO)
    service.marcar_como_lida(usuario_id, lida.id)

    notificacoes = service.listar_notificacoes(usuario_id, apenas_nao_lidas=True)

    assert len(notificacoes) == 1
    assert notificacoes[0].lida is False


def test_marcar_como_lida_marca_a_notificacao_como_lida():
    service = _service()
    usuario_id = uuid4()
    notificacao = service.enviar_alerta(usuario_id, _sinal(), _ATIVO)

    atualizada = service.marcar_como_lida(usuario_id, notificacao.id)

    assert atualizada.lida is True


def test_marcar_como_lida_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(NotificacaoNaoEncontradaError):
        service.marcar_como_lida(uuid4(), uuid4())


def test_marcar_como_lida_de_outro_usuario_lanca_erro():
    service = _service()
    usuario_id = uuid4()
    notificacao = service.enviar_alerta(usuario_id, _sinal(), _ATIVO)

    with pytest.raises(NotificacaoNaoEncontradaError):
        service.marcar_como_lida(uuid4(), notificacao.id)
