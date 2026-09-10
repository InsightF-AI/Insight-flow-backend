from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.cotacao_repository import SqlAlchemyCotacaoRepository

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


def _cotacao(ativo_id, data_hora, fechamento="35.80") -> Cotacao:
    return Cotacao(
        id=uuid4(),
        ativo_id=ativo_id,
        data_hora=data_hora,
        abertura=Decimal("35.00"),
        maxima=Decimal("36.00"),
        minima=Decimal("34.50"),
        fechamento=Decimal(fechamento),
        volume=Decimal(1000000),
    )


def test_salvar_muitas_persiste_as_cotacoes(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyCotacaoRepository(session)
    cotacoes = [
        _cotacao(ativo.id, datetime(2024, 1, 1, tzinfo=UTC)),
        _cotacao(ativo.id, datetime(2024, 1, 2, tzinfo=UTC)),
    ]

    repo.salvar_muitas(cotacoes)

    encontradas = repo.listar_por_ativo(ativo.id)
    assert len(encontradas) == 2


def test_salvar_muitas_em_conflito_atualiza_em_vez_de_duplicar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyCotacaoRepository(session)
    data_hora = datetime(2024, 1, 1, tzinfo=UTC)
    repo.salvar_muitas([_cotacao(ativo.id, data_hora, fechamento="35.80")])

    repo.salvar_muitas([_cotacao(ativo.id, data_hora, fechamento="40.00")])

    encontradas = repo.listar_por_ativo(ativo.id)
    assert len(encontradas) == 1
    assert encontradas[0].fechamento == Decimal("40.00")


def test_listar_por_ativo_retorna_ordenado_por_data_hora(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyCotacaoRepository(session)
    mais_recente = datetime(2024, 1, 2, tzinfo=UTC)
    mais_antiga = datetime(2024, 1, 1, tzinfo=UTC)
    repo.salvar_muitas([_cotacao(ativo.id, mais_recente), _cotacao(ativo.id, mais_antiga)])

    encontradas = repo.listar_por_ativo(ativo.id)

    assert [c.data_hora for c in encontradas] == [mais_antiga, mais_recente]


def test_salvar_muitas_com_data_hora_repetida_no_mesmo_lote_mantem_a_ultima(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyCotacaoRepository(session)
    data_hora = datetime(2024, 1, 1, tzinfo=UTC)

    repo.salvar_muitas(
        [
            _cotacao(ativo.id, data_hora, fechamento="35.80"),
            _cotacao(ativo.id, data_hora, fechamento="41.00"),
        ]
    )

    encontradas = repo.listar_por_ativo(ativo.id)
    assert len(encontradas) == 1
    assert encontradas[0].fechamento == Decimal("41.00")


def test_listar_por_ativo_sem_cotacoes_retorna_lista_vazia(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyCotacaoRepository(session)

    assert repo.listar_por_ativo(ativo.id) == []
