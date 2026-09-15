from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)

pytestmark = pytest.mark.integration


def _novo_ativo(session) -> Ativo:
    ativo = Ativo(
        id=uuid4(),
        ticker="PETR4",
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petróleo e Gás",
        moeda="BRL",
        fonte_dados="manual",
    )
    SqlAlchemyAtivoRepository(session).salvar(ativo)
    return ativo


def _indicador(ativo_id, tipo=TipoIndicador.SMA, periodo=20, valor="10.5") -> IndicadorTecnico:
    return IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo_id,
        tipo=tipo,
        parametros={"periodo": periodo},
        data_calculo=datetime(2024, 1, 1, tzinfo=UTC),
        valor=Decimal(valor),
        valores_auxiliares=None,
    )


def test_salvar_e_listar_por_ativo_retorna_o_indicador(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    repo.salvar(_indicador(ativo.id))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 1
    assert encontrados[0].tipo == TipoIndicador.SMA
    assert encontrados[0].parametros == {"periodo": 20}
    assert encontrados[0].valor == Decimal("10.5")


def test_salvar_em_conflito_atualiza_em_vez_de_duplicar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    repo.salvar(_indicador(ativo.id, valor="10.5"))

    repo.salvar(_indicador(ativo.id, valor="11.0"))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 1
    assert encontrados[0].valor == Decimal("11.0")


def test_indicadores_com_parametros_diferentes_nao_se_sobrescrevem(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    repo.salvar(_indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=20, valor="10.5"))
    repo.salvar(_indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=50, valor="9.0"))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 2
    valores = {i.parametros["periodo"]: i.valor for i in encontrados}
    assert valores == {20: Decimal("10.5"), 50: Decimal("9.0")}


def test_valores_auxiliares_persiste_e_retorna_o_dict(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    indicador = IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo.id,
        tipo=TipoIndicador.MACD,
        parametros={"rapida": 12, "lenta": 26, "sinal": 9},
        data_calculo=datetime(2024, 1, 1, tzinfo=UTC),
        valor=Decimal("1.5"),
        valores_auxiliares={"linha_sinal": 1.2, "histograma": 0.3},
    )

    repo.salvar(indicador)

    encontrados = repo.listar_por_ativo(ativo.id)
    assert encontrados[0].valores_auxiliares == {"linha_sinal": 1.2, "histograma": 0.3}


def test_listar_por_ativo_sem_indicadores_retorna_lista_vazia(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    assert repo.listar_por_ativo(ativo.id) == []


def test_salvar_com_parametros_em_ordem_diferente_nao_duplica(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    indicador_a = IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo.id,
        tipo=TipoIndicador.BOLLINGER,
        parametros={"periodo": 20, "desvios": 2},
        data_calculo=datetime(2024, 1, 1, tzinfo=UTC),
        valor=Decimal("10.0"),
        valores_auxiliares=None,
    )
    indicador_b = IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo.id,
        tipo=TipoIndicador.BOLLINGER,
        parametros={"desvios": 2, "periodo": 20},
        data_calculo=datetime(2024, 1, 2, tzinfo=UTC),
        valor=Decimal("11.0"),
        valores_auxiliares=None,
    )

    repo.salvar(indicador_a)
    repo.salvar(indicador_b)

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 1
    assert encontrados[0].valor == Decimal("11.0")


def test_salvar_muitas_persiste_e_atualiza_em_conflito(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    indicadores = [
        _indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=20, valor="10.5"),
        _indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=50, valor="9.0"),
        _indicador(ativo.id, tipo=TipoIndicador.RSI, periodo=14, valor="55.0"),
    ]

    repo.salvar_muitas(indicadores)

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 3

    atualizados = [
        _indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=20, valor="20.5"),
        _indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=50, valor="19.0"),
        _indicador(ativo.id, tipo=TipoIndicador.RSI, periodo=14, valor="65.0"),
    ]

    repo.salvar_muitas(atualizados)

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 3
    valores = {(i.tipo, i.parametros.get("periodo")): i.valor for i in encontrados}
    assert valores == {
        (TipoIndicador.SMA, 20): Decimal("20.5"),
        (TipoIndicador.SMA, 50): Decimal("19.0"),
        (TipoIndicador.RSI, 14): Decimal("65.0"),
    }
