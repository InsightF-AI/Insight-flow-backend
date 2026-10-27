import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.logs import em_correlacao
from app.db.models.usuario import UsuarioModel
from app.db.session import marcar_correlacao_na_transacao

pytestmark = pytest.mark.integration

_MIGRATION = Path(__file__).parents[2] / "alembic" / "versions" / "c2e8a4f6b913_cria_auditoria.py"


def _comandos_da_migration() -> list[str]:
    spec = importlib.util.spec_from_file_location("migration_auditoria", _MIGRATION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.comandos_upgrade()


@pytest.fixture
def auditada(session):
    for comando in _comandos_da_migration():
        session.execute(text(comando))
    return session


def _novo_usuario(session, nome: str = "Ana") -> UsuarioModel:
    usuario = UsuarioModel(
        id=uuid4(),
        nome=nome,
        email=f"ana-{uuid4()}@example.com",
        senha_hash="hash-secreto",
        criado_em=datetime(2026, 10, 27, tzinfo=UTC),
        ativo=True,
    )
    session.add(usuario)
    session.flush()
    return usuario


def _trilha(session, registro_id) -> list:
    return session.execute(
        text(
            "SELECT operacao, usuario_id, correlation_id, dados_antes, dados_depois "
            "FROM auditoria WHERE tabela = 'usuarios' AND registro_id = :id ORDER BY id"
        ),
        {"id": str(registro_id)},
    ).all()


def test_insert_gera_linha_sem_a_senha(auditada):
    usuario = _novo_usuario(auditada)

    [linha] = _trilha(auditada, usuario.id)
    assert linha.operacao == "INSERT"
    assert linha.usuario_id == usuario.id
    assert linha.dados_antes is None
    assert linha.dados_depois["nome"] == "Ana"
    assert "senha_hash" not in linha.dados_depois


def test_update_guarda_antes_e_depois(auditada):
    usuario = _novo_usuario(auditada)

    usuario.nome = "Ana Maria"
    auditada.flush()

    linha = _trilha(auditada, usuario.id)[-1]
    assert linha.operacao == "UPDATE"
    assert linha.dados_antes["nome"] == "Ana"
    assert linha.dados_depois["nome"] == "Ana Maria"


def test_update_so_da_senha_nao_gera_linha(auditada):
    usuario = _novo_usuario(auditada)

    usuario.senha_hash = "outro-hash"
    auditada.flush()

    assert [linha.operacao for linha in _trilha(auditada, usuario.id)] == ["INSERT"]


def test_delete_guarda_o_estado_anterior(auditada):
    usuario = _novo_usuario(auditada)

    auditada.delete(usuario)
    auditada.flush()

    linha = _trilha(auditada, usuario.id)[-1]
    assert linha.operacao == "DELETE"
    assert linha.dados_antes["email"] == usuario.email
    assert linha.dados_depois is None


def test_linha_carrega_o_correlation_id_da_requisicao(auditada):
    with em_correlacao("req-auditoria-1"):
        marcar_correlacao_na_transacao(auditada, None, auditada.connection())
        usuario = _novo_usuario(auditada)

    [linha] = _trilha(auditada, usuario.id)
    assert linha.correlation_id == "req-auditoria-1"
