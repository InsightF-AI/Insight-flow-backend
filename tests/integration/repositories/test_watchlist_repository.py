from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.ativo import Ativo
from app.domain.entities.usuario import Usuario
from app.domain.entities.watchlist import Watchlist
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository

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


def test_salvar_e_listar_por_usuario_retorna_o_item_adicionado(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyWatchlistRepository(session)
    item = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=ativo.id,
        adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
    )

    repo.salvar(item)
    itens = repo.listar_por_usuario(usuario.id)

    assert len(itens) == 1
    assert itens[0].ativo_id == ativo.id
    assert itens[0].notificar is True


def test_buscar_por_usuario_e_ativo_encontra_item_existente(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyWatchlistRepository(session)
    item = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=ativo.id,
        adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
    )
    repo.salvar(item)

    encontrado = repo.buscar_por_usuario_e_ativo(usuario.id, ativo.id)

    assert encontrado is not None
    assert encontrado.id == item.id


def test_buscar_por_usuario_e_ativo_nao_encontrado_retorna_none(session):
    repo = SqlAlchemyWatchlistRepository(session)

    assert repo.buscar_por_usuario_e_ativo(uuid4(), uuid4()) is None


def test_salvar_atualiza_flag_notificar_de_item_existente(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyWatchlistRepository(session)
    item = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=ativo.id,
        adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
    )
    repo.salvar(item)

    item.desabilitar_notificacao()
    repo.salvar(item)

    encontrado = repo.buscar_por_usuario_e_ativo(usuario.id, ativo.id)
    assert encontrado.notificar is False


def test_remover_apaga_o_item_da_watchlist(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyWatchlistRepository(session)
    item = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=ativo.id,
        adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
    )
    repo.salvar(item)

    repo.remover(item)

    assert repo.buscar_por_usuario_e_ativo(usuario.id, ativo.id) is None


def test_salvar_mesmo_usuario_e_ativo_duas_vezes_viola_constraint_unica(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyWatchlistRepository(session)
    repo.salvar(
        Watchlist.adicionar(
            id=uuid4(),
            usuario_id=usuario.id,
            ativo_id=ativo.id,
            adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
        )
    )

    with pytest.raises(IntegrityError):
        repo.salvar(
            Watchlist.adicionar(
                id=uuid4(),
                usuario_id=usuario.id,
                ativo_id=ativo.id,
                adicionado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
            )
        )
