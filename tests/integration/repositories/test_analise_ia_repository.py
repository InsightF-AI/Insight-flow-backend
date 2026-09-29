from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.analise_ia import AnaliseIA
from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.analise_ia_repository import SqlAlchemyAnaliseIARepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository

pytestmark = pytest.mark.integration


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


def _nova_analise(ativo_id, hora: int = 10, texto: str = "Analise tecnica.") -> AnaliseIA:
    return AnaliseIA(
        id=uuid4(),
        ativo_id=ativo_id,
        texto=texto,
        provedor="gemini",
        modelo="gemini-2.5-flash",
        prompt_versao="analise_ativo.v1",
        contexto_hash="a" * 64,
        gerado_em=datetime(2026, 9, 29, hora, 0, 0, tzinfo=UTC),
    )


def test_salvar_e_buscar_ultima_retorna_a_analise_criada(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAnaliseIARepository(session)
    analise = _nova_analise(ativo.id)

    repo.salvar(analise)
    encontrada = repo.buscar_ultima_por_ativo(ativo.id)

    assert encontrada is not None
    assert encontrada.id == analise.id
    assert encontrada.texto == "Analise tecnica."
    assert encontrada.provedor == "gemini"
    assert encontrada.modelo == "gemini-2.5-flash"
    assert encontrada.prompt_versao == "analise_ativo.v1"
    assert encontrada.contexto_hash == "a" * 64
    assert encontrada.gerado_em == datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)


def test_buscar_ultima_retorna_a_mais_recente(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAnaliseIARepository(session)
    repo.salvar(_nova_analise(ativo.id, hora=9, texto="antiga"))
    repo.salvar(_nova_analise(ativo.id, hora=11, texto="nova"))

    encontrada = repo.buscar_ultima_por_ativo(ativo.id)

    assert encontrada.texto == "nova"


def test_buscar_ultima_nao_mistura_ativos(session):
    ativo = _novo_ativo(session, "PETR4")
    outro = _novo_ativo(session, "VALE3")
    repo = SqlAlchemyAnaliseIARepository(session)
    repo.salvar(_nova_analise(outro.id, texto="da vale"))

    assert repo.buscar_ultima_por_ativo(ativo.id) is None


def test_texto_longo_e_persistido_sem_truncar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyAnaliseIARepository(session)
    texto = "x" * 5000
    repo.salvar(_nova_analise(ativo.id, texto=texto))

    assert repo.buscar_ultima_por_ativo(ativo.id).texto == texto
