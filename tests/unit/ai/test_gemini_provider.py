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
from app.ai.providers.gemini import GeminiProvider
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError


def _resposta_texto(texto: str) -> dict:
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": texto}]}}]}


def _provedor(handler, dormir=None) -> tuple[GeminiProvider, list]:
    esperas: list = []
    cliente = httpx.Client(base_url="https://gemini.test", transport=httpx.MockTransport(handler))
    provedor = GeminiProvider(
        cliente,
        api_key="chave-teste",
        modelo="gemini-teste",
        backoff_segundos=2.0,
        dormir=dormir or esperas.append,
    )
    return provedor, esperas


def test_gerar_texto_envia_payload_correto_e_retorna_o_texto():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        capturado["chave"] = request.headers["x-goog-api-key"]
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(200, json=_resposta_texto("Analise pronta."))

    provedor, _ = _provedor(handler)

    texto = provedor.gerar_texto("SYSTEM", "PROMPT")

    assert texto == "Analise pronta."
    assert capturado["path"] == "/v1beta/models/gemini-teste:generateContent"
    assert capturado["chave"] == "chave-teste"
    corpo = capturado["corpo"]
    assert corpo["systemInstruction"] == {"parts": [{"text": "SYSTEM"}]}
    assert corpo["contents"] == [{"role": "user", "parts": [{"text": "PROMPT"}]}]
    assert corpo["generationConfig"] == {"temperature": 0.2}
    assert "tools" not in corpo


def test_conversar_declara_ferramentas_e_interpreta_function_call():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"functionCall": {"name": "obter_posicoes", "args": {}}},
                                {
                                    "functionCall": {
                                        "name": "comparar_benchmark",
                                        "args": {"benchmark": "CDI"},
                                    }
                                },
                            ],
                        }
                    }
                ]
            },
        )

    provedor, _ = _provedor(handler)
    ferramentas = [
        DeclaracaoFerramenta(nome="obter_posicoes", descricao="Lista posicoes"),
        DeclaracaoFerramenta(
            nome="comparar_benchmark",
            descricao="Compara",
            parametros={"type": "object", "properties": {"benchmark": {"type": "string"}}},
        ),
    ]

    resposta = provedor.conversar(
        "SYSTEM",
        [MensagemChat(papel=PapelMensagem.USUARIO, texto="Como esta minha carteira?")],
        ferramentas,
    )

    assert resposta.texto == ""
    assert resposta.chamadas == (
        ChamadaFerramenta(nome="obter_posicoes", argumentos={}),
        ChamadaFerramenta(nome="comparar_benchmark", argumentos={"benchmark": "CDI"}),
    )
    declaracoes = capturado["corpo"]["tools"][0]["functionDeclarations"]
    assert declaracoes[0] == {"name": "obter_posicoes", "description": "Lista posicoes"}
    assert declaracoes[1]["parameters"]["type"] == "object"


def test_conversar_converte_historico_com_chamadas_e_resultados():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(200, json=_resposta_texto("Ok."))

    provedor, _ = _provedor(handler)
    mensagens = [
        MensagemChat(papel=PapelMensagem.USUARIO, texto="Oi"),
        MensagemChat(
            papel=PapelMensagem.ASSISTENTE,
            chamadas=(ChamadaFerramenta(nome="obter_posicoes", argumentos={}),),
        ),
        MensagemChat(
            papel=PapelMensagem.USUARIO,
            resultados=(ResultadoFerramenta(nome="obter_posicoes", conteudo={"posicoes": []}),),
        ),
    ]

    provedor.conversar("SYSTEM", mensagens, [])

    contents = capturado["corpo"]["contents"]
    assert contents[0] == {"role": "user", "parts": [{"text": "Oi"}]}
    assert contents[1] == {
        "role": "model",
        "parts": [{"functionCall": {"name": "obter_posicoes", "args": {}}}],
    }
    assert contents[2] == {
        "role": "user",
        "parts": [{"functionResponse": {"name": "obter_posicoes", "response": {"posicoes": []}}}],
    }


def test_429_duas_vezes_levanta_cota_excedida_com_retry_after_e_uma_espera():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(429, headers={"Retry-After": "7"}, json={})

    provedor, esperas = _provedor(handler)

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after == 7
    assert len(chamadas) == 2
    assert esperas == [2.0]


@pytest.mark.parametrize(("atraso", "esperado"), [("7s", 7), ("3.5s", 4), ("0.2s", 1)])
def test_429_le_retry_delay_do_corpo_quando_nao_ha_header(atraso, esperado):
    corpo = {
        "error": {
            "code": 429,
            "details": [
                {"@type": "type.googleapis.com/google.rpc.Help"},
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": atraso},
            ],
        }
    }
    provedor, _ = _provedor(lambda request: httpx.Response(429, json=corpo))

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after == esperado


def test_429_com_corpo_fora_do_formato_esperado_deixa_retry_after_none():
    provedor, _ = _provedor(lambda request: httpx.Response(429, json=["nao", "e", "dict"]))

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after is None


def test_assinatura_de_raciocinio_da_chamada_volta_no_turno_seguinte():
    corpos = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpos.append(json.loads(request.content))
        if len(corpos) == 1:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {
                            "content": {
                                "role": "model",
                                "parts": [
                                    {
                                        "functionCall": {"name": "obter_posicoes", "args": {}},
                                        "thoughtSignature": "assinatura-opaca",
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        return httpx.Response(200, json=_resposta_texto("Ok."))

    provedor, _ = _provedor(handler)
    primeira = provedor.conversar("S", [MensagemChat(papel=PapelMensagem.USUARIO, texto="Oi")], [])

    assert primeira.chamadas[0].assinatura == "assinatura-opaca"

    provedor.conversar(
        "S",
        [
            MensagemChat(papel=PapelMensagem.USUARIO, texto="Oi"),
            MensagemChat(papel=PapelMensagem.ASSISTENTE, chamadas=primeira.chamadas),
            MensagemChat(
                papel=PapelMensagem.USUARIO,
                resultados=(ResultadoFerramenta("obter_posicoes", {"posicoes": []}),),
            ),
        ],
        [],
    )

    parte_do_modelo = corpos[1]["contents"][1]["parts"][0]
    assert parte_do_modelo["thoughtSignature"] == "assinatura-opaca"
    assert parte_do_modelo["functionCall"]["name"] == "obter_posicoes"


def test_chamada_sem_assinatura_nao_envia_o_campo():
    corpos = []

    def handler(request: httpx.Request) -> httpx.Response:
        corpos.append(json.loads(request.content))
        return httpx.Response(200, json=_resposta_texto("Ok."))

    provedor, _ = _provedor(handler)
    provedor.conversar(
        "S",
        [
            MensagemChat(
                papel=PapelMensagem.ASSISTENTE,
                chamadas=(ChamadaFerramenta("obter_posicoes", {}),),
            )
        ],
        [],
    )

    assert "thoughtSignature" not in corpos[0]["contents"][0]["parts"][0]


def test_429_seguido_de_sucesso_retorna_o_texto():
    respostas = [httpx.Response(429, json={}), httpx.Response(200, json=_resposta_texto("Ok."))]

    provedor, esperas = _provedor(lambda request: respostas.pop(0))

    assert provedor.gerar_texto("S", "P") == "Ok."
    assert esperas == [2.0]


def test_429_sem_header_deixa_retry_after_none():
    provedor, _ = _provedor(lambda request: httpx.Response(429, json={}))

    with pytest.raises(LLMCotaExcedidaError) as exc_info:
        provedor.gerar_texto("S", "P")

    assert exc_info.value.retry_after is None


def test_5xx_duas_vezes_levanta_indisponivel():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(503, json={})

    provedor, _ = _provedor(handler)

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")

    assert len(chamadas) == 2


def test_4xx_levanta_indisponivel_sem_repetir():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(403, json={})

    provedor, esperas = _provedor(handler)

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")

    assert len(chamadas) == 1
    assert esperas == []


def test_timeout_levanta_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    provedor, _ = _provedor(handler)

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")


@pytest.mark.parametrize(
    "corpo",
    [
        {},
        {"candidates": []},
        {"candidates": [{"finishReason": "SAFETY"}]},
        {"candidates": [{"content": {"parts": []}}]},
    ],
)
def test_resposta_sem_conteudo_levanta_indisponivel(corpo):
    provedor, _ = _provedor(lambda request: httpx.Response(200, json=corpo))

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")


def test_corpo_que_nao_e_json_levanta_indisponivel():
    provedor, _ = _provedor(lambda request: httpx.Response(200, content=b"<html>"))

    with pytest.raises(LLMIndisponivelError):
        provedor.gerar_texto("S", "P")
