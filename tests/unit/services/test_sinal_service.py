from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.services.exceptions import AtivoNaoEncontradoError, RegraNaoEncontradaError
from app.services.indicador_service import IndicadorService
from app.services.sinal_service import SinalService, avaliar_condicao
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
from tests.fixtures.fake_sinal_repository import FakeSinalRepository

_ATIVO = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def test_avaliar_condicao_menor_que():
    condicoes = {"operador": "menor_que", "valor_limiar": 30}
    assert avaliar_condicao(condicoes, Decimal(29)) is True
    assert avaliar_condicao(condicoes, Decimal(30)) is False
    assert avaliar_condicao(condicoes, Decimal(31)) is False


def test_avaliar_condicao_maior_que():
    condicoes = {"operador": "maior_que", "valor_limiar": 70}
    assert avaliar_condicao(condicoes, Decimal(71)) is True
    assert avaliar_condicao(condicoes, Decimal(70)) is False


def test_avaliar_condicao_menor_igual():
    condicoes = {"operador": "menor_igual", "valor_limiar": 30}
    assert avaliar_condicao(condicoes, Decimal(30)) is True
    assert avaliar_condicao(condicoes, Decimal(31)) is False


def test_avaliar_condicao_maior_igual():
    condicoes = {"operador": "maior_igual", "valor_limiar": 70}
    assert avaliar_condicao(condicoes, Decimal(70)) is True
    assert avaliar_condicao(condicoes, Decimal(69)) is False


def _cotacoes_rsi_baixo(ativo_id) -> list[Cotacao]:
    precos = [20.0] * 30 + [20 - i * 1.0 for i in range(1, 11)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos)
    ]


def _cotacoes_rsi_alto(ativo_id) -> list[Cotacao]:
    precos = [10 + i * 0.1 for i in range(40)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos)
    ]


def _cotacoes_recuperacao(ativo_id, a_partir_de: datetime) -> list[Cotacao]:
    precos = [10 + i * 0.5 for i in range(1, 21)]
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=a_partir_de + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos, start=1)
    ]


def _service(ativo_repository=None, cotacao_repository=None, sinal_repository=None):
    ativo_repository = ativo_repository or FakeAtivoRepository()
    cotacao_repository = cotacao_repository or FakeCotacaoRepository()
    indicador_service = IndicadorService(
        ativo_repository, cotacao_repository, FakeIndicadorTecnicoRepository()
    )
    return SinalService(
        ativo_repository,
        cotacao_repository,
        indicador_service,
        sinal_repository or FakeSinalRepository(),
    )


_REGRA_SOBREVENDA_RSI = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")
_REGRA_SOBRECOMPRA_RSI = next(r for r in REGRAS_PADRAO if r.nome == "Sobrecompra RSI")


def test_avaliar_ativo_cria_sinal_quando_condicao_passa_a_satisfeita():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_ATIVO.id))
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)

    vigentes = service.avaliar_ativo(_ATIVO.id)

    sinais_rsi = [s for s in vigentes if s.regra_id == _REGRA_SOBREVENDA_RSI.id]
    assert len(sinais_rsi) == 1
    assert sinais_rsi[0].data_desativacao is None
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is not None


def test_avaliar_ativo_cria_sinal_de_sobrecompra_com_rsi_alto():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_alto(_ATIVO.id))
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)

    vigentes = service.avaliar_ativo(_ATIVO.id)

    sinais_rsi = [s for s in vigentes if s.regra_id == _REGRA_SOBRECOMPRA_RSI.id]
    assert len(sinais_rsi) == 1
    assert sinais_rsi[0].data_desativacao is None
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBRECOMPRA_RSI.id) is not None


def test_avaliar_ativo_mantem_o_mesmo_sinal_sem_duplicar():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_ATIVO.id))
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)
    primeira = service.avaliar_ativo(_ATIVO.id)
    id_primeiro_sinal = next(
        s.id for s in primeira if s.regra_id == _REGRA_SOBREVENDA_RSI.id
    )

    segunda = service.avaliar_ativo(_ATIVO.id)

    id_segundo_sinal = next(
        s.id for s in segunda if s.regra_id == _REGRA_SOBREVENDA_RSI.id
    )
    assert id_segundo_sinal == id_primeiro_sinal
    assert len(sinal_repository.listar_por_ativo(_ATIVO.id)) == 1


def test_avaliar_ativo_desativa_sinal_quando_condicao_deixa_de_ser_satisfeita():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    declinio = _cotacoes_rsi_baixo(_ATIVO.id)
    cotacao_repository.salvar_muitas(declinio)
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)
    service.avaliar_ativo(_ATIVO.id)
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is not None

    cotacao_repository.salvar_muitas(_cotacoes_recuperacao(_ATIVO.id, declinio[-1].data_hora))
    vigentes = service.avaliar_ativo(_ATIVO.id)

    assert all(s.regra_id != _REGRA_SOBREVENDA_RSI.id for s in vigentes)
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is None
    historico = sinal_repository.listar_por_ativo(_ATIVO.id)
    sinal_desativado = next(s for s in historico if s.regra_id == _REGRA_SOBREVENDA_RSI.id)
    assert sinal_desativado.data_desativacao is not None


def test_avaliar_ativo_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.avaliar_ativo(uuid4())


def test_score_composto_soma_pesos_das_regras_vigentes():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    sinal_repository = FakeSinalRepository()
    regra_volume = next(r for r in REGRAS_PADRAO if r.nome == "Pico de Volume")
    sinal_repository.salvar(
        Sinal(
            id=uuid4(),
            ativo_id=_ATIVO.id,
            regra_id=_REGRA_SOBREVENDA_RSI.id,
            data_ativacao=datetime.now(UTC),
            contexto={},
            data_desativacao=None,
        )
    )
    sinal_repository.salvar(
        Sinal(
            id=uuid4(),
            ativo_id=_ATIVO.id,
            regra_id=regra_volume.id,
            data_ativacao=datetime.now(UTC),
            contexto={},
            data_desativacao=None,
        )
    )
    service = _service(ativo_repository, sinal_repository=sinal_repository)

    score = service.score_composto(_ATIVO.id)

    assert score == _REGRA_SOBREVENDA_RSI.peso + regra_volume.peso


def test_score_composto_sem_sinais_vigentes_retorna_zero():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    service = _service(ativo_repository)

    assert service.score_composto(_ATIVO.id) == Decimal(0)


def _cotacoes_backtest_rsi(ativo_id) -> list[Cotacao]:
    precos = (
        [20.0] * 30
        + [20 - i * 1.0 for i in range(1, 11)]
        + [10 + i * 0.5 for i in range(1, 21)]
    )
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos)
    ]


def test_backtest_encontra_ocorrencia_e_calcula_retornos_medios():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_backtest_rsi(_ATIVO.id))
    service = _service(ativo_repository, cotacao_repository)

    resultado = service.backtest(_REGRA_SOBREVENDA_RSI.id, _ATIVO.id)

    assert resultado.regra_id == _REGRA_SOBREVENDA_RSI.id
    assert resultado.ativo_id == _ATIVO.id
    assert resultado.total_ocorrencias == 1
    assert round(resultado.retorno_medio_5_pregoes, 2) == Decimal("-26.32")
    assert round(resultado.retorno_medio_20_pregoes, 2) == Decimal("-18.42")
    assert resultado.retorno_medio_60_pregoes is None


def test_backtest_sem_ocorrencias_retorna_zero_e_janelas_nulas():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_alto(_ATIVO.id))
    service = _service(ativo_repository, cotacao_repository)

    resultado = service.backtest(_REGRA_SOBREVENDA_RSI.id, _ATIVO.id)

    assert resultado.total_ocorrencias == 0
    assert resultado.retorno_medio_5_pregoes is None
    assert resultado.retorno_medio_20_pregoes is None
    assert resultado.retorno_medio_60_pregoes is None


def test_backtest_com_regra_inexistente_lanca_erro():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    service = _service(ativo_repository)

    with pytest.raises(RegraNaoEncontradaError):
        service.backtest(uuid4(), _ATIVO.id)


def test_backtest_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.backtest(_REGRA_SOBREVENDA_RSI.id, uuid4())
