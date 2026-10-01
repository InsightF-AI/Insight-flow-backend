from uuid import uuid4

from app.ai.providers.base import ChamadaFerramenta, RespostaLLM
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError
from tests.fixtures.cenario_portfolio import ATIVO_PETR4
from tests.fixtures.cotacoes_sinteticas import gerar_cotacoes

_AVISO = "Análise gerada por IA. Não constitui recomendação de investimento."


def _preparar_ativo(ativo_repository, cotacao_repository, com_cotacoes: bool = True):
    ativo_repository.salvar(ATIVO_PETR4)
    if com_cotacoes:
        cotacao_repository.salvar_muitas(gerar_cotacoes(ATIVO_PETR4.id))


def test_analise_sem_token_retorna_401(client):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/analise")

    assert resposta.status_code == 401


def test_analise_retorna_texto_com_aviso_legal(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar("O RSI indica condicao neutra.")

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ativo_id"] == str(ATIVO_PETR4.id)
    assert corpo["texto"] == "O RSI indica condicao neutra."
    assert corpo["modelo"] == "fake-1"
    assert corpo["em_cache"] is False
    assert corpo["aviso_legal"] == _AVISO
    assert "gerado_em" in corpo


def test_segunda_chamada_vem_do_cache(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar("Primeira analise.")

    client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)
    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 200
    assert resposta.json()["em_cache"] is True
    assert len(provedor_llm.chamadas_gerar) == 1


def test_analise_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/analise", headers=auth_headers)

    assert resposta.status_code == 404


def test_analise_de_ativo_sem_cotacoes_retorna_422(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository, com_cotacoes=False)

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 422
    assert provedor_llm.chamadas_gerar == []


def test_analise_com_cota_excedida_retorna_503_com_retry_after(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar(LLMCotaExcedidaError(retry_after=7))

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "7"


def test_analise_com_cota_excedida_sem_retry_after_nao_envia_o_header(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar(LLMCotaExcedidaError())

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 503
    assert "Retry-After" not in resposta.headers


def test_analise_com_provedor_indisponivel_retorna_503(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar(LLMIndisponivelError())

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 503


def test_analise_com_duas_violacoes_retorna_502(
    client, auth_headers, ativo_repository, cotacao_repository, provedor_llm
):
    _preparar_ativo(ativo_repository, cotacao_repository)
    provedor_llm.enfileirar("Compre agora.", "Venda tudo.")

    resposta = client.get(f"/api/v1/ativos/{ATIVO_PETR4.id}/analise", headers=auth_headers)

    assert resposta.status_code == 502


def _corpo_chat(*mensagens: tuple[str, str]) -> dict:
    return {"mensagens": [{"papel": papel, "texto": texto} for papel, texto in mensagens]}


def test_chat_sem_token_retorna_401(client):
    resposta = client.post("/api/v1/chat", json=_corpo_chat(("usuario", "Oi")))

    assert resposta.status_code == 401


def test_chat_retorna_resposta_com_aviso_legal(client, auth_headers, provedor_llm):
    provedor_llm.enfileirar("Sua carteira esta vazia.")

    resposta = client.post(
        "/api/v1/chat",
        json=_corpo_chat(("usuario", "Como esta minha carteira?")),
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    assert resposta.json() == {
        "texto": "Sua carteira esta vazia.",
        "modelo": "fake-1",
        "aviso_legal": _AVISO,
    }


def test_chat_executa_ferramentas_com_a_carteira_do_usuario_autenticado(
    client, auth_headers, ativo_repository, provedor_llm
):
    ativo_repository.salvar(ATIVO_PETR4)
    provedor_llm.enfileirar(
        RespostaLLM(chamadas=(ChamadaFerramenta("listar_operacoes", {}),)), "Nenhuma operacao."
    )

    resposta = client.post(
        "/api/v1/chat",
        json=_corpo_chat(("usuario", "Quais minhas operacoes?")),
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    assert resposta.json()["texto"] == "Nenhuma operacao."
    resultado = provedor_llm.chamadas_conversar[1][1][2].resultados[0]
    assert resultado.conteudo == {"operacoes": []}


def test_chat_com_lista_vazia_retorna_422(client, auth_headers):
    resposta = client.post("/api/v1/chat", json={"mensagens": []}, headers=auth_headers)

    assert resposta.status_code == 422


def test_chat_com_ultima_mensagem_do_assistente_retorna_422(client, auth_headers):
    resposta = client.post(
        "/api/v1/chat",
        json=_corpo_chat(("usuario", "Oi"), ("assistente", "Ola")),
        headers=auth_headers,
    )

    assert resposta.status_code == 422


def test_chat_com_texto_vazio_retorna_422(client, auth_headers):
    resposta = client.post("/api/v1/chat", json=_corpo_chat(("usuario", "")), headers=auth_headers)

    assert resposta.status_code == 422


def test_chat_com_mensagem_maior_que_o_limite_retorna_422(client, auth_headers):
    resposta = client.post(
        "/api/v1/chat", json=_corpo_chat(("usuario", "x" * 2001)), headers=auth_headers
    )

    assert resposta.status_code == 422


def test_chat_com_mais_mensagens_que_o_limite_retorna_422(client, auth_headers):
    mensagens = [("usuario" if i % 2 == 0 else "assistente", "oi") for i in range(21)]

    resposta = client.post("/api/v1/chat", json=_corpo_chat(*mensagens), headers=auth_headers)

    assert resposta.status_code == 422


def test_chat_com_papel_invalido_retorna_422(client, auth_headers):
    resposta = client.post(
        "/api/v1/chat", json=_corpo_chat(("sistema", "Oi")), headers=auth_headers
    )

    assert resposta.status_code == 422


def test_chat_com_provedor_indisponivel_retorna_503(client, auth_headers, provedor_llm):
    provedor_llm.enfileirar(LLMIndisponivelError())

    resposta = client.post(
        "/api/v1/chat", json=_corpo_chat(("usuario", "Oi")), headers=auth_headers
    )

    assert resposta.status_code == 503


def test_chat_com_cota_excedida_retorna_503_com_retry_after(client, auth_headers, provedor_llm):
    provedor_llm.enfileirar(LLMCotaExcedidaError(retry_after=12))

    resposta = client.post(
        "/api/v1/chat", json=_corpo_chat(("usuario", "Oi")), headers=auth_headers
    )

    assert resposta.status_code == 503
    assert resposta.headers["Retry-After"] == "12"


def test_chat_com_duas_violacoes_retorna_502(client, auth_headers, provedor_llm):
    provedor_llm.enfileirar("Compre agora.", "Venda tudo.")

    resposta = client.post(
        "/api/v1/chat", json=_corpo_chat(("usuario", "Oi")), headers=auth_headers
    )

    assert resposta.status_code == 502
