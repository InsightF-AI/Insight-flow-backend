import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.ai.providers.base import (
    ChamadaFerramenta,
    DeclaracaoFerramenta,
    MensagemChat,
    PapelMensagem,
    ResultadoFerramenta,
)
from app.ai.providers.claude import ClaudeProvider
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError


def _texto(texto: str):
    return SimpleNamespace(type="text", text=texto)


def _tool_use(id_: str, nome: str, entrada: dict):
    return SimpleNamespace(type="tool_use", id=id_, name=nome, input=entrada)


def _resposta(*blocos, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocos), stop_reason=stop_reason)


class _ClienteFalso:
    def __init__(self, *respostas):
        self._respostas = list(respostas)
        self.parametros: list[dict] = []
        self.messages = self

    def create(self, **parametros):
        self.parametros.append(parametros)
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _provedor(*respostas) -> tuple[ClaudeProvider, _ClienteFalso]:
    cliente = _ClienteFalso(*respostas)
    return ClaudeProvider(cliente, "claude-haiku-5-5", "medium"), cliente


def _erro_http(classe, status: int, headers: dict | None = None):
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    resposta = httpx2.Response(status, headers=headers or {}, request=requisicao)
    return classe("erro", response=resposta, body=None)


def test_gerar_texto_envia_modelo_system_esforco_e_sem_temperatura():
    provedor, cliente = _provedor(_resposta(_texto("Analise "), _texto("pronta.")))

    texto = provedor.gerar_texto("SYSTEM", "PROMPT")

    assert texto == "Analise pronta."
    parametros = cliente.parametros[0]
    assert parametros["model"] == "claude-haiku-5-5"
    assert parametros["system"] == "SYSTEM"
    assert parametros["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "PROMPT"}]}
    ]
    assert parametros["output_config"] == {"effort": "medium"}
    assert "temperature" not in parametros
    assert "thinking" not in parametros
    assert "tools" not in parametros


def test_conversar_declara_ferramentas_e_interpreta_tool_use():
    pensamento = SimpleNamespace(type="thinking", thinking="", signature="sig")
    resposta = _resposta(
        pensamento,
        _tool_use("toolu_1", "comparar_benchmark", {"benchmark": "CDI"}),
        stop_reason="tool_use",
    )
    provedor, cliente = _provedor(resposta)
    ferramentas = [
        DeclaracaoFerramenta("obter_posicoes", "Lista posicoes"),
        DeclaracaoFerramenta("comparar_benchmark", "Compara", {"type": "object", "properties": {}}),
    ]

    resultado = provedor.conversar("S", [MensagemChat(PapelMensagem.USUARIO, "oi")], ferramentas)

    assert resultado.chamadas == (
        ChamadaFerramenta("comparar_benchmark", {"benchmark": "CDI"}, id="toolu_1"),
    )
    assert resultado.estado == [pensamento, resposta.content[1]]
    tools = cliente.parametros[0]["tools"]
    assert tools[0] == {
        "name": "obter_posicoes",
        "description": "Lista posicoes",
        "input_schema": {"type": "object", "properties": {}},
    }
    assert tools[1]["input_schema"] == {"type": "object", "properties": {}}


def test_historico_reenvia_o_estado_bruto_e_resultados_com_tool_use_id():
    provedor, cliente = _provedor(_resposta(_texto("ok")))
    estado = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    mensagens = [
        MensagemChat(PapelMensagem.USUARIO, "quanto tenho?"),
        MensagemChat(
            PapelMensagem.ASSISTENTE,
            chamadas=(ChamadaFerramenta("obter_posicoes", {}, id="toolu_1"),),
            estado=estado,
        ),
        MensagemChat(
            PapelMensagem.USUARIO,
            resultados=(ResultadoFerramenta("obter_posicoes", {"valor": "10"}, id="toolu_1"),),
        ),
    ]

    provedor.conversar("S", mensagens, [])

    enviadas = cliente.parametros[0]["messages"]
    assert enviadas[1] == {"role": "assistant", "content": estado}
    assert enviadas[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": json.dumps({"valor": "10"}),
            }
        ],
    }


def test_mensagem_do_assistente_sem_estado_vira_blocos_de_texto():
    provedor, cliente = _provedor(_resposta(_texto("ok")))

    provedor.conversar(
        "S",
        [
            MensagemChat(PapelMensagem.USUARIO, "oi"),
            MensagemChat(PapelMensagem.ASSISTENTE, "ola"),
            MensagemChat(PapelMensagem.USUARIO, "tudo bem?"),
        ],
        [],
    )

    assert cliente.parametros[0]["messages"][1] == {
        "role": "assistant",
        "content": [{"type": "text", "text": "ola"}],
    }


def test_recusa_vira_indisponivel():
    provedor, _ = _provedor(_resposta(stop_reason="refusal"))

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")


def test_resposta_vazia_por_max_tokens_vira_indisponivel():
    provedor, _ = _provedor(
        _resposta(SimpleNamespace(type="thinking", thinking=""), stop_reason="max_tokens")
    )

    with pytest.raises(LLMIndisponivelError, match="max_tokens"):
        provedor.gerar_texto("S", "P")


def test_rate_limit_vira_cota_excedida_com_retry_after():
    provedor, _ = _provedor(_erro_http(anthropic.RateLimitError, 429, {"retry-after": "17"}))

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after == 17


def test_erro_de_status_vira_indisponivel():
    provedor, _ = _provedor(_erro_http(anthropic.InternalServerError, 500))

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")


def test_erro_de_conexao_vira_indisponivel():
    requisicao = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    provedor, _ = _provedor(anthropic.APIConnectionError(request=requisicao))

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")
