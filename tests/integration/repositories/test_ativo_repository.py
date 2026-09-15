from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository

pytestmark = pytest.mark.integration


def _novo_ativo(ticker: str = "PETR4") -> Ativo:
    return Ativo(
        id=uuid4(),
        ticker=ticker,
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petróleo e Gás",
        moeda="BRL",
        fonte_dados="manual",
    )


def test_salvar_e_buscar_por_id_retorna_o_mesmo_ativo(session):
    repo = SqlAlchemyAtivoRepository(session)
    ativo = _novo_ativo()

    repo.salvar(ativo)
    encontrado = repo.buscar_por_id(ativo.id)

    assert encontrado is not None
    assert encontrado.ticker == "PETR4"
    assert encontrado.tipo is TipoAtivo.ACAO


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyAtivoRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_buscar_por_ticker_encontra_ativo_cadastrado(session):
    repo = SqlAlchemyAtivoRepository(session)
    ativo = _novo_ativo(ticker="VALE3")
    repo.salvar(ativo)

    encontrado = repo.buscar_por_ticker("VALE3")

    assert encontrado is not None
    assert encontrado.id == ativo.id


def test_buscar_por_ticker_nao_encontrado_retorna_none(session):
    repo = SqlAlchemyAtivoRepository(session)

    assert repo.buscar_por_ticker("NAOEXISTE") is None


def test_salvar_dois_ativos_com_mesmo_ticker_viola_constraint_unica(session):
    repo = SqlAlchemyAtivoRepository(session)
    repo.salvar(_novo_ativo(ticker="ITUB4"))

    with pytest.raises(IntegrityError):
        repo.salvar(_novo_ativo(ticker="ITUB4"))
