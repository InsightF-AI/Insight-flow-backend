import json

import httpx
import pytest

from app.ai.providers.base import (
    ChamadaFerramenta,
    DeclaracaoFerramenta,
    MensagemChat,
    PapelMensagem,
    ResultadoFerramenta,
)
from app.ai.providers.openai_compativel import OpenAICompativelProvider
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError


def _provedor(handler, api_key: str = "chave") -> OpenAICompativelProvider:
    cliente = httpx.Client(base_url="https://llm.test", transport=httpx.MockTransport(handler))
    return OpenAICompativelProvider(cliente, "openai", "modelo-x", api_key)


def _mensagem(**mensagem) -> dict:
    return {"choices": [{"message": {"role": "assistant", **mensagem}}]}


def test_gerar_texto_envia_system_e_autenticacao():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        capturado["auth"] = request.headers.get("Authorization")
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(200, json=_mensagem(content="Pronto."))

    texto = _provedor(handler).gerar_texto("SYSTEM", "PROMPT")

    assert texto == "Pronto."
    assert capturado["path"] == "/v1/chat/completions"
    assert capturado["auth"] == "Bearer chave"
    assert capturado["corpo"] == {
        "model": "modelo-x",
        "messages": [
            {"role": "system", "content": "SYSTEM"},
            {"role": "user", "content": "PROMPT"},
        ],
    }


def test_sem_chave_nao_envia_authorization():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json=_mensagem(content="ok"))

    _provedor(handler, api_key="").gerar_texto("S", "P")

    assert capturado["auth"] is None


def test_ferramentas_e_historico_no_formato_openai():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_mensagem(
                content=None,
                tool_calls=[
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "comparar_benchmark",
                            "arguments": '{"benchmark": "CDI"}',
                        },
                    }
                ],
            ),
        )

    mensagens = [
        MensagemChat(PapelMensagem.USUARIO, "oi"),
        MensagemChat(
            PapelMensagem.ASSISTENTE,
            chamadas=(ChamadaFerramenta("obter_posicoes", {}, id="call_1"),),
        ),
        MensagemChat(
            PapelMensagem.USUARIO,
            resultados=(ResultadoFerramenta("obter_posicoes", {"n": 1}, id="call_1"),),
        ),
    ]
    ferramentas = [
        DeclaracaoFerramenta("obter_posicoes", "Lista"),
        DeclaracaoFerramenta("comparar_benchmark", "Compara", {"type": "object"}),
    ]

    resposta = _provedor(handler).conversar("S", mensagens, ferramentas)

    assert resposta.chamadas == (
        ChamadaFerramenta("comparar_benchmark", {"benchmark": "CDI"}, id="call_2"),
    )
    corpo = capturado["corpo"]
    assert corpo["messages"][2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "obter_posicoes", "arguments": "{}"},
            }
        ],
    }
    assert corpo["messages"][3] == {"role": "tool", "tool_call_id": "call_1", "content": '{"n": 1}'}
    assert corpo["tools"] == [
        {"type": "function", "function": {"name": "obter_posicoes", "description": "Lista"}},
        {
            "type": "function",
            "function": {
                "name": "comparar_benchmark",
                "description": "Compara",
                "parameters": {"type": "object"},
            },
        },
    ]


def test_429_vira_cota_excedida():
    provedor = _provedor(lambda _: httpx.Response(429, headers={"Retry-After": "9"}))

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after == 9


@pytest.mark.parametrize("status", [400, 500])
def test_erro_http_vira_indisponivel(status):
    with pytest.raises(LLMIndisponivelError):
        _provedor(lambda _: httpx.Response(status)).gerar_texto("S", "P")


def test_argumentos_invalidos_viram_indisponivel():
    corpo = _mensagem(
        content=None,
        tool_calls=[{"id": "c", "function": {"name": "x", "arguments": "{nao json"}}],
    )

    with pytest.raises(LLMIndisponivelError):
        _provedor(lambda _: httpx.Response(200, json=corpo)).conversar("S", [], [])


def test_resposta_vazia_vira_indisponivel():
    with pytest.raises(LLMIndisponivelError):
        _provedor(lambda _: httpx.Response(200, json=_mensagem(content=""))).gerar_texto("S", "P")
