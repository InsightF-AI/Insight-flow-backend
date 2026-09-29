from uuid import uuid4

from app.ai.ferramentas_chat import ExecutorFerramentas
from app.ai.providers.base import ChamadaFerramenta
from tests.fixtures.cenario_portfolio import (
    ATIVO_PETR4,
    ATIVO_VALE3,
    cotacao_atual,
    montar_portfolio_service,
    nova_operacao,
)
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository


def _executor(operacoes):
    ativo_repository = FakeAtivoRepository()
    portfolio_service = montar_portfolio_service(
        [ATIVO_PETR4, ATIVO_VALE3],
        operacoes,
        {"PETR4": cotacao_atual("PETR4", "35.00"), "VALE3": cotacao_atual("VALE3", "60.00")},
        ativo_repository=ativo_repository,
    )
    return ExecutorFerramentas(portfolio_service, ativo_repository)


def test_declaracoes_expoem_as_cinco_ferramentas():
    nomes = [d.nome for d in _executor([]).declaracoes()]

    assert nomes == [
        "obter_posicoes",
        "obter_rentabilidade",
        "obter_distribuicao",
        "listar_operacoes",
        "comparar_benchmark",
    ]


def test_comparar_benchmark_declara_enum_de_benchmark():
    declaracao = next(d for d in _executor([]).declaracoes() if d.nome == "comparar_benchmark")

    assert declaracao.parametros["properties"]["benchmark"]["enum"] == ["CDI", "IBOVESPA"]


def test_obter_posicoes_retorna_posicoes_serializadas():
    usuario_id = uuid4()
    executor = _executor([nova_operacao(usuario_id, ATIVO_PETR4.id)])

    resultado = executor.executar(usuario_id, ChamadaFerramenta("obter_posicoes", {}))

    assert resultado.nome == "obter_posicoes"
    posicao = resultado.conteudo["posicoes"][0]
    assert posicao["ticker"] == "PETR4"
    assert posicao["quantidade"] == "10"
    assert posicao["cotacao_atual"] == "35.00"


def test_obter_rentabilidade_e_distribuicao_retornam_dicts_serializados():
    usuario_id = uuid4()
    executor = _executor([nova_operacao(usuario_id, ATIVO_PETR4.id)])

    rentabilidade = executor.executar(usuario_id, ChamadaFerramenta("obter_rentabilidade", {}))
    distribuicao = executor.executar(usuario_id, ChamadaFerramenta("obter_distribuicao", {}))

    assert "percentual" in rentabilidade.conteudo
    assert distribuicao.conteudo["por_classe"] == {"ACAO": "1"}


def test_listar_operacoes_retorna_apenas_as_do_usuario_e_ignora_usuario_id_do_modelo():
    usuario_id = uuid4()
    outro_usuario_id = uuid4()
    executor = _executor(
        [
            nova_operacao(usuario_id, ATIVO_PETR4.id),
            nova_operacao(outro_usuario_id, ATIVO_VALE3.id, dia=2),
            nova_operacao(outro_usuario_id, ATIVO_VALE3.id, dia=3),
        ]
    )

    resultado = executor.executar(
        usuario_id,
        ChamadaFerramenta("listar_operacoes", {"usuario_id": str(outro_usuario_id)}),
    )

    operacoes = resultado.conteudo["operacoes"]
    assert len(operacoes) == 1
    assert operacoes[0]["ticker"] == "PETR4"


def test_listar_operacoes_expoe_ticker_e_nao_vaza_ids():
    usuario_id = uuid4()
    executor = _executor([nova_operacao(usuario_id, ATIVO_PETR4.id)])

    resultado = executor.executar(usuario_id, ChamadaFerramenta("listar_operacoes", {}))

    assert resultado.conteudo["operacoes"] == [
        {
            "ticker": "PETR4",
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        }
    ]


def test_falha_inesperada_em_ferramenta_vira_erro_para_a_llm_sem_estourar():
    class _PortfolioQuebrado:
        def posicoes(self, usuario_id):
            raise RuntimeError("cambio fora do ar")

    executor = ExecutorFerramentas(_PortfolioQuebrado(), FakeAtivoRepository())

    resultado = executor.executar(uuid4(), ChamadaFerramenta("obter_posicoes", {}))

    assert resultado.nome == "obter_posicoes"
    assert resultado.conteudo == {"erro": "dado indisponivel"}


def test_comparar_benchmark_com_argumento_invalido_devolve_erro_para_a_llm():
    usuario_id = uuid4()
    executor = _executor([nova_operacao(usuario_id, ATIVO_PETR4.id)])

    resultado = executor.executar(
        usuario_id, ChamadaFerramenta("comparar_benchmark", {"benchmark": "SELIC"})
    )

    assert "erro" in resultado.conteudo


def test_comparar_benchmark_sem_argumento_devolve_erro_para_a_llm():
    resultado = _executor([]).executar(uuid4(), ChamadaFerramenta("comparar_benchmark", {}))

    assert "erro" in resultado.conteudo


def test_comparar_benchmark_sem_operacoes_devolve_erro_para_a_llm():
    resultado = _executor([]).executar(
        uuid4(), ChamadaFerramenta("comparar_benchmark", {"benchmark": "CDI"})
    )

    assert resultado.conteudo == {"erro": "nenhuma operacao registrada"}


def test_comparar_benchmark_cdi_retorna_comparativo():
    usuario_id = uuid4()
    executor = _executor([nova_operacao(usuario_id, ATIVO_PETR4.id)])

    resultado = executor.executar(
        usuario_id, ChamadaFerramenta("comparar_benchmark", {"benchmark": "CDI"})
    )

    assert resultado.conteudo["benchmark"] == "CDI"
    assert "rentabilidade_carteira_percentual" in resultado.conteudo


def test_ferramenta_desconhecida_devolve_erro_para_a_llm():
    resultado = _executor([]).executar(uuid4(), ChamadaFerramenta("apagar_tudo", {}))

    assert resultado.conteudo == {"erro": "ferramenta desconhecida: apagar_tudo"}
