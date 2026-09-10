from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_indicador import TipoIndicador
from app.services.indicador_service import IndicadorService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository

_ATIVO_ID = uuid4()


def _cotacoes(fechamentos: list[str], volumes: list[str] | None = None) -> list[Cotacao]:
    volumes = volumes or ["1000000"] * len(fechamentos)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=_ATIVO_ID,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(fechamento),
            maxima=Decimal(fechamento),
            minima=Decimal(fechamento),
            fechamento=Decimal(fechamento),
            volume=Decimal(volume),
        )
        for i, (fechamento, volume) in enumerate(zip(fechamentos, volumes, strict=True))
    ]


def _service() -> IndicadorService:
    return IndicadorService(
        FakeAtivoRepository(), FakeCotacaoRepository(), FakeIndicadorTecnicoRepository()
    )


def test_calcular_sma_com_precos_constantes_retorna_o_proprio_preco():
    cotacoes = _cotacoes(["10"] * 20)
    service = _service()

    indicador = service.calcular_sma(cotacoes, periodo=20)

    assert indicador is not None
    assert indicador.ativo_id == _ATIVO_ID
    assert indicador.tipo == TipoIndicador.SMA
    assert indicador.parametros == {"periodo": 20}
    assert indicador.valor == Decimal(10)
    assert indicador.valores_auxiliares is None


def test_calcular_sma_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_sma(cotacoes, periodo=20) is None


def test_calcular_sma_com_lista_vazia_retorna_none():
    service = _service()

    assert service.calcular_sma([], periodo=20) is None


def test_calcular_rsi_com_precos_variaveis_retorna_indicador_valido():
    fechamentos = [str(10 + i * 0.1) for i in range(20)]
    cotacoes = _cotacoes(fechamentos)
    service = _service()

    indicador = service.calcular_rsi(cotacoes, periodo=14)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.RSI
    assert indicador.parametros == {"periodo": 14}
    assert Decimal(0) <= indicador.valor <= Decimal(100)


def test_calcular_rsi_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_rsi(cotacoes, periodo=14) is None


def test_calcular_macd_com_historico_suficiente_retorna_indicador_com_auxiliares():
    fechamentos = [str(10 + i * 0.1) for i in range(60)]
    cotacoes = _cotacoes(fechamentos)
    service = _service()

    indicador = service.calcular_macd(cotacoes)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.MACD
    assert indicador.parametros == {"rapida": 12, "lenta": 26, "sinal": 9}
    assert indicador.valores_auxiliares is not None
    assert "linha_sinal" in indicador.valores_auxiliares
    assert "histograma" in indicador.valores_auxiliares


def test_calcular_macd_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10"] * 5)
    service = _service()

    assert service.calcular_macd(cotacoes) is None


def test_calcular_bollinger_com_precos_constantes_bandas_iguais_ao_preco():
    cotacoes = _cotacoes(["10"] * 20)
    service = _service()

    indicador = service.calcular_bollinger(cotacoes, periodo=20, desvios=2)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.BOLLINGER
    assert indicador.parametros == {"periodo": 20, "desvios": 2}
    assert indicador.valor == Decimal(10)
    assert indicador.valores_auxiliares == {"banda_superior": 10.0, "banda_inferior": 10.0}


def test_calcular_bollinger_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_bollinger(cotacoes, periodo=20, desvios=2) is None


def test_calcular_volume_relativo_com_volume_constante_retorna_um():
    cotacoes = _cotacoes(["10"] * 20, volumes=["500000"] * 20)
    service = _service()

    indicador = service.calcular_volume_relativo(cotacoes, periodo=20)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.VOLUME_RELATIVO
    assert indicador.parametros == {"periodo": 20}
    assert indicador.valor == Decimal(1)
    assert indicador.valores_auxiliares is None


def test_calcular_volume_relativo_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_volume_relativo(cotacoes, periodo=20) is None
