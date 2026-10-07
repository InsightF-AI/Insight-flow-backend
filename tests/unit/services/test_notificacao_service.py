import logging
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
from app.notifications.canal import CanalNotificacao, CanalTempoReal
from app.services.exceptions import NotificacaoNaoEncontradaError
from app.services.notificacao_service import NotificacaoService
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
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
        volume=Decimal(1000000),
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


def test_enviar_resumo_diario_persiste_notificacao_sem_ativo_com_texto_no_contexto():
    repository = FakeNotificacaoRepository()
    service = NotificacaoService(repository)
    usuario_id = uuid4()
    texto = "x" * 2000

    notificacao = service.enviar_resumo_diario(
        usuario_id, texto, {"modelo": "gemini-2.5-flash", "prompt_versao": "resumo_diario.v1"}
    )

    assert notificacao.tipo == TipoNotificacao.RESUMO_DIARIO
    assert notificacao.ativo_id is None
    assert notificacao.usuario_id == usuario_id
    assert notificacao.mensagem == "Resumo diario da carteira"
    assert len(notificacao.mensagem) <= 255
    assert notificacao.contexto["texto"] == texto
    assert notificacao.contexto["aviso_legal"] == (
        "Análise gerada por IA. Não constitui recomendação de investimento."
    )
    assert notificacao.contexto["modelo"] == "gemini-2.5-flash"
    assert repository.buscar_por_id(notificacao.id) == notificacao


def test_buscar_ultimo_resumo_diario_retorna_o_mais_recente_do_usuario():
    repository = FakeNotificacaoRepository()
    service = NotificacaoService(repository)
    usuario_id = uuid4()
    service.enviar_resumo_diario(usuario_id, "antigo", {})
    recente = service.enviar_resumo_diario(usuario_id, "recente", {})
    recente.criado_em = datetime(2100, 1, 1, tzinfo=UTC)
    service.enviar_resumo_diario(uuid4(), "de outro usuario", {})

    ultimo = service.buscar_ultimo_resumo_diario(usuario_id)

    assert ultimo.id == recente.id


def test_buscar_ultimo_resumo_diario_sem_resumos_retorna_none():
    service = NotificacaoService(FakeNotificacaoRepository())

    assert service.buscar_ultimo_resumo_diario(uuid4()) is None


class _CanalQueFalha(CanalNotificacao):
    def entregar(self, notificacao) -> None:
        raise RuntimeError("canal fora do ar")


class _CanalQueRegistra(CanalNotificacao):
    def __init__(self) -> None:
        self.entregues = []

    def entregar(self, notificacao) -> None:
        self.entregues.append(notificacao)


def _alerta_e_cotacao():
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
        minima_dia=Decimal("40.00"),
        volume=Decimal(1000),
    )
    return alerta, cotacao


def test_resumo_diario_e_entregue_em_todos_os_canais():
    repositorio = FakeNotificacaoRepository()
    primeiro = _CanalQueRegistra()
    segundo = _CanalQueRegistra()
    service = NotificacaoService(repositorio, canais=[primeiro, segundo])

    resumo = service.enviar_resumo_diario(uuid4(), "Texto do resumo", {})

    assert primeiro.entregues == [resumo]
    assert segundo.entregues == [resumo]
    assert repositorio.buscar_por_id(resumo.id) == resumo


def test_alerta_de_sinal_e_entregue_nos_canais():
    registrador = _CanalQueRegistra()
    service = NotificacaoService(FakeNotificacaoRepository(), canais=[registrador])

    notificacao = service.enviar_alerta(uuid4(), _sinal(), _ATIVO)

    assert registrador.entregues == [notificacao]


def test_alerta_personalizado_e_entregue_nos_canais():
    registrador = _CanalQueRegistra()
    service = NotificacaoService(FakeNotificacaoRepository(), canais=[registrador])
    alerta, cotacao = _alerta_e_cotacao()

    notificacao = service.enviar_alerta_personalizado(alerta.usuario_id, alerta, cotacao)

    assert registrador.entregues == [notificacao]


def test_falha_de_um_canal_nao_impede_gravacao_nem_os_demais_canais():
    repositorio = FakeNotificacaoRepository()
    registrador = _CanalQueRegistra()
    service = NotificacaoService(repositorio, canais=[_CanalQueFalha(), registrador])

    resumo = service.enviar_resumo_diario(uuid4(), "Texto do resumo", {})

    assert repositorio.buscar_por_id(resumo.id) == resumo
    assert registrador.entregues == [resumo]


def test_barramento_fora_do_ar_nao_impede_a_gravacao():
    repositorio = FakeNotificacaoRepository()
    barramento = FakeBarramentoNotificacoes()
    barramento.falhar = True
    service = NotificacaoService(repositorio, canais=[CanalTempoReal(barramento)])

    resumo = service.enviar_resumo_diario(uuid4(), "Texto do resumo", {})

    assert repositorio.buscar_por_id(resumo.id) == resumo


def test_marcar_como_lida_nao_entrega_nos_canais():
    registrador = _CanalQueRegistra()
    service = NotificacaoService(FakeNotificacaoRepository(), canais=[registrador])
    usuario_id = uuid4()
    resumo = service.enviar_resumo_diario(usuario_id, "Texto do resumo", {})
    registrador.entregues.clear()

    service.marcar_como_lida(usuario_id, resumo.id)

    assert registrador.entregues == []


def test_notificacao_enviada_e_logada_com_tipo_usuario_e_ativo(caplog):
    service = _service()
    usuario_id = uuid4()
    caplog.set_level(logging.INFO)

    service.enviar_alerta(usuario_id, _sinal(), _ATIVO)

    registro = next(
        r for r in caplog.records if getattr(r, "evento", None) == "notificacao_enviada"
    )
    assert registro.tipo == "SINAL_ATIVADO"
    assert registro.usuario_id == str(usuario_id)
    assert registro.ativo_id == str(_ATIVO.id)
