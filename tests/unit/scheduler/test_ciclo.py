from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.ativo import Ativo
from app.domain.entities.sinal import Sinal
from app.domain.entities.watchlist import Watchlist
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.scheduler.ciclo import executar_ciclo_monitoramento
from app.services.alerta_service import AlertaService
from app.services.ativo_service import AtivoService
from app.services.indicador_service import IndicadorService
from app.services.notificacao_service import NotificacaoService
from app.services.sinal_service import SinalService
from tests.fixtures.fake_alerta_repository import FakeAlertaRepository
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_sinal_repository import FakeSinalRepository
from tests.fixtures.fake_watchlist_repository import FakeWatchlistRepository

_REGRA_RSI_BAIXO = REGRAS_PADRAO[0]


@dataclass
class _Ciclo:
    ativo_repository: FakeAtivoRepository
    watchlist_repository: FakeWatchlistRepository
    alerta_repository: FakeAlertaRepository
    sinal_repository: FakeSinalRepository
    cotacao_repository: FakeCotacaoRepository
    dados_mercado_service: FakeDadosMercadoService
    ativo_service: AtivoService
    alerta_service: AlertaService
    sinal_service: SinalService
    notificacao_service: NotificacaoService
    notificacao_repository: FakeNotificacaoRepository


def _construir_ciclo(dados_mercado_service: FakeDadosMercadoService | None = None) -> _Ciclo:
    ativo_repository = FakeAtivoRepository()
    watchlist_repository = FakeWatchlistRepository()
    alerta_repository = FakeAlertaRepository()
    sinal_repository = FakeSinalRepository()
    cotacao_repository = FakeCotacaoRepository()
    dados_mercado_service = dados_mercado_service or FakeDadosMercadoService()
    notificacao_repository = FakeNotificacaoRepository()
    indicador_service = IndicadorService(
        ativo_repository, cotacao_repository, FakeIndicadorTecnicoRepository()
    )
    return _Ciclo(
        ativo_repository=ativo_repository,
        watchlist_repository=watchlist_repository,
        alerta_repository=alerta_repository,
        sinal_repository=sinal_repository,
        cotacao_repository=cotacao_repository,
        dados_mercado_service=dados_mercado_service,
        ativo_service=AtivoService(ativo_repository, dados_mercado_service, cotacao_repository),
        alerta_service=AlertaService(
            alerta_repository, ativo_repository, dados_mercado_service, FakeCambioService()
        ),
        sinal_service=SinalService(
            ativo_repository, cotacao_repository, indicador_service, sinal_repository
        ),
        notificacao_service=NotificacaoService(notificacao_repository),
        notificacao_repository=notificacao_repository,
    )


def _executar(ciclo: _Ciclo, tipos_ativo: set[TipoAtivo]) -> None:
    executar_ciclo_monitoramento(
        tipos_ativo,
        ciclo.ativo_repository,
        ciclo.watchlist_repository,
        ciclo.alerta_repository,
        ciclo.sinal_repository,
        ciclo.dados_mercado_service,
        ciclo.ativo_service,
        ciclo.alerta_service,
        ciclo.sinal_service,
        ciclo.notificacao_service,
    )


def _ativo(ticker: str = "PETR4", tipo: TipoAtivo = TipoAtivo.ACAO) -> Ativo:
    return Ativo(
        id=uuid4(),
        ticker=ticker,
        nome=ticker,
        tipo=tipo,
        setor="Petroleo e Gas" if tipo != TipoAtivo.CRIPTO else None,
        moeda="BRL" if tipo != TipoAtivo.CRIPTO else "USD",
        fonte_dados="manual",
    )


def _cotacao(ticker: str, preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker=ticker,
        preco=Decimal(preco),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal(1000),
    )


def _alerta(usuario_id, ativo_id, moeda_alvo: str = "BRL") -> AlertaPersonalizado:
    return AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("35.00"),
        moeda_alvo=moeda_alvo,
        criado_em=datetime.now(UTC),
    )


def _historico_rsi_baixo() -> list[PontoHistorico]:
    precos = [20.0] * 30 + [20 - i * 1.0 for i in range(1, 11)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        PontoHistorico(
            data=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos)
    ]


def test_universo_filtra_por_tipo_de_ativo():
    ativo_acao = _ativo("PETR4", TipoAtivo.ACAO)
    ativo_cripto = _ativo("BTC", TipoAtivo.CRIPTO)
    dados_mercado_service = FakeDadosMercadoService(
        cotacoes={"PETR4": _cotacao("PETR4", "40.00"), "BTC": _cotacao("BTC", "40.00")}
    )
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo_acao)
    ciclo.ativo_repository.salvar(ativo_cripto)
    usuario_acao = uuid4()
    usuario_cripto = uuid4()
    ciclo.alerta_repository.salvar(_alerta(usuario_acao, ativo_acao.id))
    ciclo.alerta_repository.salvar(_alerta(usuario_cripto, ativo_cripto.id, moeda_alvo="USD"))

    _executar(ciclo, {TipoAtivo.ACAO})

    assert len(ciclo.notificacao_repository.listar_por_usuario(usuario_acao)) == 1
    assert ciclo.notificacao_repository.listar_por_usuario(usuario_cripto) == []


def test_ativo_so_com_alerta_nao_recalcula_indicadores():
    ativo = _ativo()
    dados_mercado_service = FakeDadosMercadoService(
        cotacoes={"PETR4": _cotacao("PETR4", "40.00")},
        historicos={"PETR4": _historico_rsi_baixo()},
    )
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo)
    ciclo.alerta_repository.salvar(_alerta(uuid4(), ativo.id))

    _executar(ciclo, {TipoAtivo.ACAO})

    assert ciclo.cotacao_repository.listar_por_ativo(ativo.id) == []


def test_alerta_disparado_notifica_apenas_o_dono():
    ativo = _ativo()
    dados_mercado_service = FakeDadosMercadoService(cotacoes={"PETR4": _cotacao("PETR4", "40.00")})
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo)
    usuario_id = uuid4()
    ciclo.alerta_repository.salvar(_alerta(usuario_id, ativo.id))

    _executar(ciclo, {TipoAtivo.ACAO})

    notificacoes = ciclo.notificacao_repository.listar_por_usuario(usuario_id)
    assert len(notificacoes) == 1
    assert notificacoes[0].tipo == TipoNotificacao.ALERTA_DISPARADO


def test_sinal_novo_notifica_apenas_quem_tem_notificar_habilitado():
    ativo = _ativo()
    dados_mercado_service = FakeDadosMercadoService(
        cotacoes={"PETR4": _cotacao("PETR4", "10.00")},
        historicos={"PETR4": _historico_rsi_baixo()},
    )
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo)
    usuario_com_notificacao = uuid4()
    usuario_sem_notificacao = uuid4()
    watchlist_com = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario_com_notificacao,
        ativo_id=ativo.id,
        adicionado_em=datetime.now(UTC),
    )
    watchlist_sem = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario_sem_notificacao,
        ativo_id=ativo.id,
        adicionado_em=datetime.now(UTC),
    )
    watchlist_sem.desabilitar_notificacao()
    ciclo.watchlist_repository.salvar(watchlist_com)
    ciclo.watchlist_repository.salvar(watchlist_sem)

    _executar(ciclo, {TipoAtivo.ACAO})

    assert len(ciclo.notificacao_repository.listar_por_usuario(usuario_com_notificacao)) == 1
    assert ciclo.notificacao_repository.listar_por_usuario(usuario_sem_notificacao) == []


def test_sinal_ja_vigente_nao_gera_notificacao_duplicada():
    ativo = _ativo()
    dados_mercado_service = FakeDadosMercadoService(
        cotacoes={"PETR4": _cotacao("PETR4", "10.00")},
        historicos={"PETR4": _historico_rsi_baixo()},
    )
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo)
    usuario_id = uuid4()
    ciclo.watchlist_repository.salvar(
        Watchlist.adicionar(
            id=uuid4(), usuario_id=usuario_id, ativo_id=ativo.id, adicionado_em=datetime.now(UTC)
        )
    )
    ciclo.sinal_repository.salvar(
        Sinal(
            id=uuid4(),
            ativo_id=ativo.id,
            regra_id=_REGRA_RSI_BAIXO.id,
            data_ativacao=datetime.now(UTC) - timedelta(days=1),
            contexto={"valor": "20"},
        )
    )

    _executar(ciclo, {TipoAtivo.ACAO})

    assert ciclo.notificacao_repository.listar_por_usuario(usuario_id) == []


def test_falha_em_um_ativo_nao_impede_processamento_dos_demais():
    ativo_ok = _ativo("PETR4")
    ativo_sem_cotacao = _ativo("VALE3")
    dados_mercado_service = FakeDadosMercadoService(cotacoes={"PETR4": _cotacao("PETR4", "40.00")})
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo_ok)
    ciclo.ativo_repository.salvar(ativo_sem_cotacao)
    usuario_ok = uuid4()
    ciclo.alerta_repository.salvar(_alerta(usuario_ok, ativo_ok.id))
    ciclo.alerta_repository.salvar(_alerta(uuid4(), ativo_sem_cotacao.id))

    _executar(ciclo, {TipoAtivo.ACAO})

    assert len(ciclo.notificacao_repository.listar_por_usuario(usuario_ok)) == 1


def test_falha_em_ativo_invoca_callback_ao_falhar_ativo():
    ativo_sem_cotacao = _ativo("VALE3")
    dados_mercado_service = FakeDadosMercadoService()
    ciclo = _construir_ciclo(dados_mercado_service)
    ciclo.ativo_repository.salvar(ativo_sem_cotacao)
    ciclo.alerta_repository.salvar(_alerta(uuid4(), ativo_sem_cotacao.id))

    chamadas = 0

    def _ao_falhar_ativo() -> None:
        nonlocal chamadas
        chamadas += 1

    executar_ciclo_monitoramento(
        {TipoAtivo.ACAO},
        ciclo.ativo_repository,
        ciclo.watchlist_repository,
        ciclo.alerta_repository,
        ciclo.sinal_repository,
        ciclo.dados_mercado_service,
        ciclo.ativo_service,
        ciclo.alerta_service,
        ciclo.sinal_service,
        ciclo.notificacao_service,
        ao_falhar_ativo=_ao_falhar_ativo,
    )

    assert chamadas == 1
