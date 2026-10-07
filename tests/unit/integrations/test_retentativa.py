import httpx
import pytest

from app.integrations.retentativa import PoliticaRetentativa, executar_com_retentativa

_REQUEST = httpx.Request("GET", "https://exemplo.com/recurso")


def _resposta(status_code: int, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, headers=headers, request=_REQUEST)


class _Sequencia:
    def __init__(self, *resultados):
        self._resultados = list(resultados)
        self.chamadas = 0

    def __call__(self) -> httpx.Response:
        self.chamadas += 1
        resultado = self._resultados.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def _executar(requisicao, politica: PoliticaRetentativa | None = None):
    esperas: list[float] = []
    resposta = executar_com_retentativa(
        requisicao,
        politica or PoliticaRetentativa(tentativas=3, backoff_base_segundos=0.5),
        descricao="teste",
        dormir=esperas.append,
        aleatorio=lambda: 1.0,
    )
    return resposta, esperas


def test_sucesso_na_primeira_tentativa_nao_espera():
    requisicao = _Sequencia(_resposta(200))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == 200
    assert requisicao.chamadas == 1
    assert esperas == []


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
def test_status_transitorio_e_retentado_com_backoff_exponencial(status_code):
    requisicao = _Sequencia(_resposta(status_code), _resposta(status_code), _resposta(200))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == 200
    assert requisicao.chamadas == 3
    assert esperas == [0.5, 1.0]


def test_erro_de_rede_e_retentado():
    requisicao = _Sequencia(httpx.ConnectError("falhou", request=_REQUEST), _resposta(200))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == 200
    assert esperas == [0.5]


@pytest.mark.parametrize("status_code", [400, 401, 404])
def test_outros_erros_4xx_nao_sao_retentados(status_code):
    requisicao = _Sequencia(_resposta(status_code))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == status_code
    assert requisicao.chamadas == 1
    assert esperas == []


def test_esgotadas_as_tentativas_devolve_a_ultima_resposta():
    requisicao = _Sequencia(_resposta(503), _resposta(503), _resposta(503))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == 503
    assert requisicao.chamadas == 3
    assert esperas == [0.5, 1.0]


def test_esgotadas_as_tentativas_relanca_o_ultimo_erro_de_rede():
    erro = httpx.ReadTimeout("lento", request=_REQUEST)
    requisicao = _Sequencia(erro, erro, erro)

    with pytest.raises(httpx.ReadTimeout):
        _executar(requisicao)

    assert requisicao.chamadas == 3


def test_retry_after_define_a_espera():
    requisicao = _Sequencia(_resposta(429, {"Retry-After": "3"}), _resposta(200))

    resposta, esperas = _executar(requisicao)

    assert resposta.status_code == 200
    assert esperas == [3.0]


def test_retry_after_acima_do_teto_desiste_sem_esperar():
    requisicao = _Sequencia(_resposta(429, {"Retry-After": "120"}), _resposta(200))
    politica = PoliticaRetentativa(
        tentativas=3, backoff_base_segundos=0.5, espera_maxima_segundos=10.0
    )

    resposta, esperas = _executar(requisicao, politica)

    assert resposta.status_code == 429
    assert requisicao.chamadas == 1
    assert esperas == []


def test_retry_after_invalido_usa_o_backoff():
    requisicao = _Sequencia(_resposta(429, {"Retry-After": "amanha"}), _resposta(200))

    _, esperas = _executar(requisicao)

    assert esperas == [0.5]


def test_backoff_e_limitado_pelo_teto():
    requisicao = _Sequencia(*[_resposta(503)] * 4, _resposta(200))
    politica = PoliticaRetentativa(
        tentativas=5, backoff_base_segundos=2.0, espera_maxima_segundos=5.0
    )

    _, esperas = _executar(requisicao, politica)

    assert esperas == [2.0, 4.0, 5.0, 5.0]


def test_jitter_reduz_a_espera_pela_metade_no_minimo():
    requisicao = _Sequencia(_resposta(503), _resposta(200))
    esperas: list[float] = []

    executar_com_retentativa(
        requisicao,
        PoliticaRetentativa(tentativas=2, backoff_base_segundos=1.0),
        descricao="teste",
        dormir=esperas.append,
        aleatorio=lambda: 0.0,
    )

    assert esperas == [0.5]


def test_uma_tentativa_nao_retenta():
    requisicao = _Sequencia(_resposta(503))

    resposta, esperas = _executar(requisicao, PoliticaRetentativa(tentativas=1))

    assert resposta.status_code == 503
    assert esperas == []
