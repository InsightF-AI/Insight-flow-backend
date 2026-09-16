from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.notificacao import Notificacao
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.notificacao_repository import SqlAlchemyNotificacaoRepository
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
        setor="Petróleo e Gás",
        moeda="BRL",
        fonte_dados="manual",
    )
    SqlAlchemyAtivoRepository(session).salvar(ativo)
    return ativo


def _nova_notificacao(usuario_id, ativo_id, lida: bool = False) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo=TipoNotificacao.ALERTA_DISPARADO,
        mensagem="PETR4 atingiu o alvo de 40.00 BRL (preco maior ou igual)",
        contexto={"valor_alvo": "40.00"},
        criado_em=datetime(2026, 9, 16, 10, 0, 0, tzinfo=UTC),
        lida=lida,
    )


def test_salvar_e_buscar_por_id_retorna_a_notificacao_criada(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyNotificacaoRepository(session)
    notificacao = _nova_notificacao(usuario.id, ativo.id)

    repo.salvar(notificacao)
    encontrada = repo.buscar_por_id(notificacao.id)

    assert encontrada is not None
    assert encontrada.usuario_id == usuario.id
    assert encontrada.ativo_id == ativo.id
    assert encontrada.tipo == TipoNotificacao.ALERTA_DISPARADO
    assert encontrada.mensagem == notificacao.mensagem
    assert encontrada.contexto == {"valor_alvo": "40.00"}
    assert encontrada.lida is False


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyNotificacaoRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_listar_por_usuario_retorna_apenas_as_do_usuario(session):
    usuario = _novo_usuario(session)
    outro_usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyNotificacaoRepository(session)
    repo.salvar(_nova_notificacao(usuario.id, ativo.id))
    repo.salvar(_nova_notificacao(outro_usuario.id, ativo.id))

    notificacoes = repo.listar_por_usuario(usuario.id)

    assert len(notificacoes) == 1
    assert notificacoes[0].usuario_id == usuario.id


def test_listar_por_usuario_com_apenas_nao_lidas_filtra_as_lidas(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyNotificacaoRepository(session)
    nao_lida = _nova_notificacao(usuario.id, ativo.id, lida=False)
    lida = _nova_notificacao(usuario.id, ativo.id, lida=True)
    repo.salvar(nao_lida)
    repo.salvar(lida)

    notificacoes = repo.listar_por_usuario(usuario.id, apenas_nao_lidas=True)

    assert len(notificacoes) == 1
    assert notificacoes[0].id == nao_lida.id


def test_salvar_atualiza_notificacao_existente(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyNotificacaoRepository(session)
    notificacao = _nova_notificacao(usuario.id, ativo.id)
    repo.salvar(notificacao)

    notificacao.lida = True
    repo.salvar(notificacao)

    encontrada = repo.buscar_por_id(notificacao.id)
    assert encontrada.lida is True
