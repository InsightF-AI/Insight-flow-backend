from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.analise_ia_service import AnaliseIAService
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    ContextoInsuficienteError,
    LLMCotaExcedidaError,
    LLMIndisponivelError,
    RespostaViolaGuardrailError,
)
from app.services.indicador_service import IndicadorService
from app.services.sinal_service import SinalService
from tests.fixtures.cotacoes_sinteticas import gerar_cotacoes
from tests.fixtures.fake_analise_ia_repository import FakeAnaliseIARepository
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
from tests.fixtures.fake_provedor_llm import FakeProvedorLLM
from tests.fixtures.fake_sinal_repository import FakeSinalRepository

_ATIVO = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def _montar(cotacoes):
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(cotacoes)
    analise_repository = FakeAnaliseIARepository()
    provedor = FakeProvedorLLM()
    indicador_service = IndicadorService(
        ativo_repository, cotacao_repository, FakeIndicadorTecnicoRepository()
    )
    sinal_service = SinalService(
        ativo_repository, cotacao_repository, indicador_service, FakeSinalRepository()
    )
    service = AnaliseIAService(
        ativo_repository,
        cotacao_repository,
        indicador_service,
        sinal_service,
        analise_repository,
        provedor,
    )
    return service, provedor, cotacao_repository, analise_repository


@pytest.fixture
def cenario():
    return _montar(gerar_cotacoes(_ATIVO.id))


def test_analisar_ativo_gera_e_persiste_a_analise(cenario):
    service, provedor, _, analise_repository = cenario
    provedor.enfileirar("O RSI indica condicao neutra.")

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.em_cache is False
    assert resultado.analise.texto == "O RSI indica condicao neutra."
    assert resultado.analise.ativo_id == _ATIVO.id
    assert resultado.analise.provedor == "fake"
    assert resultado.analise.modelo == "fake-1"
    assert resultado.analise.prompt_versao == "analise_ativo.v1"
    assert len(resultado.analise.contexto_hash) == 64
    assert analise_repository.buscar_ultima_por_ativo(_ATIVO.id) == resultado.analise
    assert len(provedor.chamadas_gerar) == 1


def test_prompt_enviado_tem_os_dados_do_backend_e_nao_tem_data_de_calculo(cenario):
    service, provedor, _, _ = cenario
    provedor.enfileirar("Texto neutro.")

    service.analisar_ativo(_ATIVO.id)

    _, prompt = provedor.chamadas_gerar[0]
    assert "PETR4" in prompt
    assert "RSI" in prompt
    assert "SMA" in prompt
    assert "data_calculo" not in prompt


def test_analisar_ativo_usa_cache_quando_hash_nao_muda(cenario):
    service, provedor, _, analise_repository = cenario
    provedor.enfileirar("Primeira analise.")

    primeira = service.analisar_ativo(_ATIVO.id)
    segunda = service.analisar_ativo(_ATIVO.id)

    assert segunda.em_cache is True
    assert segunda.analise.id == primeira.analise.id
    assert len(provedor.chamadas_gerar) == 1
    assert len(analise_repository.listar_todas()) == 1


def test_novo_candle_invalida_o_cache(cenario):
    service, provedor, cotacao_repository, analise_repository = cenario
    provedor.enfileirar("Primeira analise.", "Segunda analise.")
    service.analisar_ativo(_ATIVO.id)
    nova = gerar_cotacoes(_ATIVO.id, quantidade=61)[-1]
    nova.fechamento = Decimal(90)
    cotacao_repository.salvar_muitas([nova])

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.em_cache is False
    assert resultado.analise.texto == "Segunda analise."
    assert len(analise_repository.listar_todas()) == 2


def test_mudanca_de_prompt_versao_invalida_o_cache(cenario, monkeypatch):
    service, provedor, _, _ = cenario
    provedor.enfileirar("Primeira analise.", "Segunda analise.")
    service.analisar_ativo(_ATIVO.id)
    monkeypatch.setattr("app.services.analise_ia_service.PROMPT_VERSAO_ANALISE", "analise_ativo.v2")

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.em_cache is False
    assert resultado.analise.prompt_versao == "analise_ativo.v2"


def test_mudanca_de_modelo_invalida_o_cache(cenario):
    service, provedor, _, _ = cenario
    provedor.enfileirar("Primeira analise.", "Segunda analise.")
    service.analisar_ativo(_ATIVO.id)
    provedor.modelo = "fake-2"

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.em_cache is False
    assert resultado.analise.modelo == "fake-2"


def test_violacao_regenera_com_system_reforcado_e_persiste_so_o_texto_limpo(cenario):
    service, provedor, _, analise_repository = cenario
    provedor.enfileirar("Compre agora.", "O RSI indica condicao neutra.")

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.analise.texto == "O RSI indica condicao neutra."
    assert len(provedor.chamadas_gerar) == 2
    assert "ATENCAO" in provedor.chamadas_gerar[1][0]
    assert len(analise_repository.listar_todas()) == 1


def test_duas_violacoes_levantam_erro_e_nao_persistem(cenario):
    service, provedor, _, analise_repository = cenario
    provedor.enfileirar("Compre agora.", "Venda tudo.")

    with pytest.raises(RespostaViolaGuardrailError):
        service.analisar_ativo(_ATIVO.id)

    assert analise_repository.listar_todas() == []


def test_falha_do_provedor_nao_persiste(cenario):
    service, provedor, _, analise_repository = cenario
    provedor.enfileirar(LLMIndisponivelError("fora do ar"))

    with pytest.raises(LLMIndisponivelError):
        service.analisar_ativo(_ATIVO.id)

    assert analise_repository.listar_todas() == []


def test_ativo_sem_cotacoes_levanta_contexto_insuficiente_sem_chamar_a_llm():
    service, provedor, _, _ = _montar([])

    with pytest.raises(ContextoInsuficienteError):
        service.analisar_ativo(_ATIVO.id)

    assert provedor.chamadas_gerar == []


def test_ativo_inexistente_levanta_erro(cenario):
    service, _, _, _ = cenario

    with pytest.raises(AtivoNaoEncontradoError):
        service.analisar_ativo(uuid4())


def test_gerado_em_e_timezone_aware(cenario):
    service, provedor, _, _ = cenario
    provedor.enfileirar("Texto neutro.")

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.analise.gerado_em.tzinfo is not None
    assert resultado.analise.gerado_em <= datetime.now(UTC)


def _invalidar_cache(cotacao_repository) -> None:
    nova = gerar_cotacoes(_ATIVO.id, quantidade=61)[-1]
    nova.fechamento = Decimal(90)
    cotacao_repository.salvar_muitas([nova])


@pytest.mark.parametrize(
    "falha",
    [LLMIndisponivelError("fora"), LLMCotaExcedidaError(30), RespostaViolaGuardrailError("x")],
)
def test_falha_do_provedor_devolve_a_analise_anterior_marcada_como_desatualizada(cenario, falha):
    service, provedor, cotacao_repository, _ = cenario
    provedor.enfileirar("Primeira analise.")
    primeira = service.analisar_ativo(_ATIVO.id)
    _invalidar_cache(cotacao_repository)
    provedor.enfileirar(falha)

    resultado = service.analisar_ativo(_ATIVO.id)

    assert resultado.analise.id == primeira.analise.id
    assert resultado.desatualizada is True


def test_falha_do_provedor_sem_analise_anterior_propaga_o_erro(cenario):
    service, provedor, _, _ = cenario
    provedor.enfileirar(LLMIndisponivelError("fora"))

    with pytest.raises(LLMIndisponivelError):
        service.analisar_ativo(_ATIVO.id)


def test_analise_gerada_ou_em_cache_nao_e_desatualizada(cenario):
    service, provedor, _, _ = cenario
    provedor.enfileirar("Primeira analise.")

    assert service.analisar_ativo(_ATIVO.id).desatualizada is False
    assert service.analisar_ativo(_ATIVO.id).desatualizada is False
