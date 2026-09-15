from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.ativo import Ativo
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository

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


def _sinal(ativo_id, regra_id=None, data_desativacao=None) -> Sinal:
    return Sinal(
        id=uuid4(),
        ativo_id=ativo_id,
        regra_id=regra_id or uuid4(),
        data_ativacao=datetime(2024, 1, 1, tzinfo=UTC),
        contexto={"valor": "25.5"},
        data_desativacao=data_desativacao,
    )


def test_salvar_e_buscar_ativo_retorna_o_sinal_vigente(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    sinal = _sinal(ativo.id, regra_id=regra_id)

    repo.salvar(sinal)

    encontrado = repo.buscar_ativo(ativo.id, regra_id)
    assert encontrado is not None
    assert encontrado.id == sinal.id
    assert encontrado.data_desativacao is None


def test_buscar_ativo_sem_sinal_vigente_retorna_none(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)

    assert repo.buscar_ativo(ativo.id, uuid4()) is None


def test_buscar_ativo_ignora_sinal_ja_desativado(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    repo.salvar(_sinal(ativo.id, regra_id=regra_id, data_desativacao=datetime(2024, 2, 1, tzinfo=UTC)))

    assert repo.buscar_ativo(ativo.id, regra_id) is None


def test_salvar_atualiza_sinal_existente_em_vez_de_duplicar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    sinal = _sinal(ativo.id, regra_id=regra_id)
    repo.salvar(sinal)

    sinal.data_desativacao = datetime(2024, 3, 1, tzinfo=UTC)
    repo.salvar(sinal)

    assert repo.buscar_ativo(ativo.id, regra_id) is None
    todos = repo.listar_por_ativo(ativo.id)
    assert len(todos) == 1
    assert todos[0].data_desativacao == datetime(2024, 3, 1, tzinfo=UTC)


def test_listar_por_ativo_retorna_ativos_e_desativados(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    repo.salvar(_sinal(ativo.id))
    repo.salvar(_sinal(ativo.id, data_desativacao=datetime(2024, 2, 1, tzinfo=UTC)))

    assert len(repo.listar_por_ativo(ativo.id)) == 2


def test_listar_por_ativo_sem_sinais_retorna_lista_vazia(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)

    assert repo.listar_por_ativo(ativo.id) == []


def test_salvar_sinal_vigente_duplicado_para_mesma_regra_levanta_integrity_error(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    repo.salvar(_sinal(ativo.id, regra_id=regra_id))

    with pytest.raises(IntegrityError):
        repo.salvar(_sinal(ativo.id, regra_id=regra_id))
