from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.operacao import Operacao
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_operacao import TipoOperacao
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration


def _novo_usuario(session) -> Usuario:
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email=f"ana-{uuid4()}@example.com",
        senha="segredo123",
        criado_em=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )
    SqlAlchemyUsuarioRepository(session).salvar(usuario)
    return usuario


def _novo_ativo(session, ticker: str = "PETR4") -> Ativo:
    ativo = Ativo(
        id=uuid4(),
        ticker=ticker,
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petroleo e Gas",
        moeda="BRL",
        fonte_dados="manual",
    )
    SqlAlchemyAtivoRepository(session).salvar(ativo)
    return ativo


def _nova_operacao(usuario_id, ativo_id, tipo=TipoOperacao.COMPRA) -> Operacao:
    return Operacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo=tipo,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
        criado_em=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
    )


def test_salvar_e_buscar_por_id_retorna_a_operacao_criada(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    operacao = _nova_operacao(usuario.id, ativo.id)

    repo.salvar(operacao)
    encontrada = repo.buscar_por_id(operacao.id)

    assert encontrada is not None
    assert encontrada.usuario_id == usuario.id
    assert encontrada.ativo_id == ativo.id
    assert encontrada.tipo == TipoOperacao.COMPRA
    assert encontrada.quantidade == Decimal("10")
    assert encontrada.preco_unitario == Decimal("30.00")
    assert encontrada.data == date(2026, 9, 1)


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyOperacaoRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_listar_por_usuario_retorna_apenas_as_do_usuario(session):
    usuario = _novo_usuario(session)
    outro_usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    repo.salvar(_nova_operacao(usuario.id, ativo.id))
    repo.salvar(_nova_operacao(outro_usuario.id, ativo.id))

    operacoes = repo.listar_por_usuario(usuario.id)

    assert len(operacoes) == 1
    assert operacoes[0].usuario_id == usuario.id


def test_remover_apaga_a_operacao(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    operacao = _nova_operacao(usuario.id, ativo.id)
    repo.salvar(operacao)

    repo.remover(operacao)

    assert repo.buscar_por_id(operacao.id) is None
