from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.ativo import Ativo
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.repositories.sqlalchemy.alerta_repository import SqlAlchemyAlertaRepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
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


def _novo_alerta(usuario_id, ativo_id, valor_alvo=Decimal("40.00"), moeda_alvo="BRL"):
    return AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=valor_alvo,
        moeda_alvo=moeda_alvo,
        criado_em=datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
    )


def test_salvar_e_buscar_por_id_retorna_o_alerta_criado(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAlertaRepository(session)
    alerta = _novo_alerta(usuario.id, ativo.id)

    repo.salvar(alerta)
    encontrado = repo.buscar_por_id(alerta.id)

    assert encontrado is not None
    assert encontrado.usuario_id == usuario.id
    assert encontrado.ativo_id == ativo.id
    assert encontrado.tipo_condicao == TipoCondicaoAlerta.PRECO_MAIOR_IGUAL
    assert encontrado.valor_alvo == Decimal("40.00")
    assert encontrado.moeda_alvo == "BRL"
    assert encontrado.ativo is True
    assert encontrado.ultimo_estado is False


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyAlertaRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_listar_por_usuario_retorna_apenas_os_do_usuario(session):
    usuario = _novo_usuario(session)
    outro_usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAlertaRepository(session)
    repo.salvar(_novo_alerta(usuario.id, ativo.id))
    repo.salvar(_novo_alerta(outro_usuario.id, ativo.id))

    alertas = repo.listar_por_usuario(usuario.id)

    assert len(alertas) == 1
    assert alertas[0].usuario_id == usuario.id


def test_listar_ativos_por_ativo_ignora_alertas_desativados(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAlertaRepository(session)
    alerta_ativo = _novo_alerta(usuario.id, ativo.id)
    alerta_inativo = _novo_alerta(usuario.id, ativo.id, valor_alvo=Decimal("50.00"))
    alerta_inativo.ativo = False
    repo.salvar(alerta_ativo)
    repo.salvar(alerta_inativo)

    alertas = repo.listar_ativos_por_ativo(ativo.id)

    assert len(alertas) == 1
    assert alertas[0].id == alerta_ativo.id


def test_salvar_atualiza_alerta_existente(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAlertaRepository(session)
    alerta = _novo_alerta(usuario.id, ativo.id)
    repo.salvar(alerta)

    alerta.valor_alvo = Decimal("45.00")
    alerta.avaliar(Decimal("45.00"), datetime(2026, 9, 9, 11, 0, 0, tzinfo=UTC))
    repo.salvar(alerta)

    encontrado = repo.buscar_por_id(alerta.id)
    assert encontrado.valor_alvo == Decimal("45.00")
    assert encontrado.ultimo_estado is True
    assert encontrado.disparado_em == datetime(2026, 9, 9, 11, 0, 0, tzinfo=UTC)


def test_remover_apaga_o_alerta(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAlertaRepository(session)
    alerta = _novo_alerta(usuario.id, ativo.id)
    repo.salvar(alerta)

    repo.remover(alerta)

    assert repo.buscar_por_id(alerta.id) is None
