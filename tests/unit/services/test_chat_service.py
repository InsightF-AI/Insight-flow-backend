from uuid import uuid4

import pytest

from app.ai.ferramentas_chat import ExecutorFerramentas
from app.ai.providers.base import (
    ChamadaFerramenta,
    MensagemChat,
    PapelMensagem,
    RespostaLLM,
)
from app.services.chat_service import ChatService
from app.services.exceptions import LLMIndisponivelError, RespostaViolaGuardrailError
from tests.fixtures.cenario_portfolio import (
    ATIVO_PETR4,
    cotacao_atual,
    montar_portfolio_service,
    nova_operacao,
)
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_provedor_llm import FakeProvedorLLM


def _pergunta(texto: str = "Como esta minha carteira?") -> list[MensagemChat]:
    return [MensagemChat(papel=PapelMensagem.USUARIO, texto=texto)]


def _service(max_iteracoes: int = 4):
    usuario_id = uuid4()
    ativo_repository = FakeAtivoRepository()
    portfolio_service = montar_portfolio_service(
        [ATIVO_PETR4],
        [nova_operacao(usuario_id, ATIVO_PETR4.id)],
        {"PETR4": cotacao_atual("PETR4", "35.00")},
        ativo_repository=ativo_repository,
    )
    provedor = FakeProvedorLLM()
    service = ChatService(
        provedor, ExecutorFerramentas(portfolio_service, ativo_repository), max_iteracoes
    )
    return service, usuario_id, provedor


def test_resposta_direta_sem_ferramentas_retorna_texto_e_modelo():
    service, usuario_id, provedor = _service()
    provedor.enfileirar("Sua carteira tem um ativo.")

    resposta = service.responder(usuario_id, _pergunta())

    assert resposta.texto == "Sua carteira tem um ativo."
    assert resposta.modelo == "fake-1"
    assert len(provedor.chamadas_conversar) == 1
    system, mensagens, ferramentas = provedor.chamadas_conversar[0]
    assert "ferramentas" in system
    assert mensagens == _pergunta()
    assert len(ferramentas) == 5


def test_chamada_de_ferramenta_executa_e_devolve_o_resultado_para_a_llm():
    service, usuario_id, provedor = _service()
    provedor.enfileirar(
        RespostaLLM(chamadas=(ChamadaFerramenta("obter_posicoes", {}),)),
        "Voce tem 10 cotas de PETR4.",
    )

    resposta = service.responder(usuario_id, _pergunta())

    assert resposta.texto == "Voce tem 10 cotas de PETR4."
    assert len(provedor.chamadas_conversar) == 2
    historico = provedor.chamadas_conversar[1][1]
    assert historico[1].papel == PapelMensagem.ASSISTENTE
    assert historico[1].chamadas == (ChamadaFerramenta("obter_posicoes", {}),)
    assert historico[2].papel == PapelMensagem.USUARIO
    resultado = historico[2].resultados[0]
    assert resultado.nome == "obter_posicoes"
    assert resultado.conteudo["posicoes"][0]["ticker"] == "PETR4"


def test_varias_chamadas_na_mesma_resposta_geram_varios_resultados():
    service, usuario_id, provedor = _service()
    provedor.enfileirar(
        RespostaLLM(
            chamadas=(
                ChamadaFerramenta("obter_posicoes", {}),
                ChamadaFerramenta("obter_rentabilidade", {}),
            )
        ),
        "Resumo pronto.",
    )

    service.responder(usuario_id, _pergunta())

    resultados = provedor.chamadas_conversar[1][1][2].resultados
    assert [r.nome for r in resultados] == ["obter_posicoes", "obter_rentabilidade"]


def test_ferramenta_desconhecida_vira_resultado_de_erro_sem_derrubar_o_chat():
    service, usuario_id, provedor = _service()
    provedor.enfileirar(
        RespostaLLM(chamadas=(ChamadaFerramenta("apagar_tudo", {}),)), "Nao tenho esse dado."
    )

    resposta = service.responder(usuario_id, _pergunta())

    assert resposta.texto == "Nao tenho esse dado."
    resultado = provedor.chamadas_conversar[1][1][2].resultados[0]
    assert "erro" in resultado.conteudo


def test_estouro_de_iteracoes_levanta_indisponivel():
    service, usuario_id, provedor = _service(max_iteracoes=2)
    chamada = RespostaLLM(chamadas=(ChamadaFerramenta("obter_posicoes", {}),))
    provedor.enfileirar(chamada, chamada, chamada)

    with pytest.raises(LLMIndisponivelError):
        service.responder(usuario_id, _pergunta())

    assert len(provedor.chamadas_conversar) == 3


def test_violacao_na_resposta_final_regenera_com_system_reforcado():
    service, usuario_id, provedor = _service()
    provedor.enfileirar("Compre mais PETR4.", "A carteira tem um ativo.")

    resposta = service.responder(usuario_id, _pergunta())

    assert resposta.texto == "A carteira tem um ativo."
    assert "ATENCAO" in provedor.chamadas_conversar[1][0]
    assert provedor.chamadas_conversar[1][1] == _pergunta()


def test_duas_violacoes_levantam_erro():
    service, usuario_id, provedor = _service()
    provedor.enfileirar("Compre mais PETR4.", "Venda tudo.")

    with pytest.raises(RespostaViolaGuardrailError):
        service.responder(usuario_id, _pergunta())


def test_recusa_educada_de_recomendacao_passa_pelo_guardrail_sem_regenerar():
    service, usuario_id, provedor = _service()
    recusa = (
        "O sistema não emite recomendações de investimento. "
        "Sua posição em PETR4 é de 10 cotas, com preço médio de 30.00."
    )
    provedor.enfileirar(recusa)

    resposta = service.responder(usuario_id, _pergunta("Devo vender PETR4?"))

    assert resposta.texto == recusa
    assert len(provedor.chamadas_conversar) == 1


def test_historico_do_usuario_nao_e_mutado():
    service, usuario_id, provedor = _service()
    provedor.enfileirar(RespostaLLM(chamadas=(ChamadaFerramenta("obter_posicoes", {}),)), "Pronto.")
    mensagens = _pergunta()

    service.responder(usuario_id, mensagens)

    assert mensagens == _pergunta()
