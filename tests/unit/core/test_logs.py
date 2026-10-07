import json
import logging
import sys
import threading

import pytest

from app.core.logs import (
    FormatadorJson,
    FormatadorTexto,
    configurar_logs,
    correlation_id_atual,
    em_correlacao,
    id_de_correlacao_valido,
)


def _registro(mensagem: str = "evento", nivel: int = logging.INFO, **extras) -> logging.LogRecord:
    registro = logging.getLogRecordFactory()(
        name="app.teste",
        level=nivel,
        pathname=__file__,
        lineno=1,
        msg=mensagem,
        args=(),
        exc_info=None,
    )
    for chave, valor in extras.items():
        setattr(registro, chave, valor)
    return registro


def test_formatador_json_gera_os_campos_padrao():
    with em_correlacao("abc123"):
        linha = FormatadorJson().format(_registro("Login realizado."))

    dados = json.loads(linha)
    assert dados["mensagem"] == "Login realizado."
    assert dados["nivel"] == "INFO"
    assert dados["logger"] == "app.teste"
    assert dados["correlation_id"] == "abc123"
    assert dados["timestamp"].endswith("Z")


def test_formatador_json_inclui_campos_extras():
    linha = FormatadorJson().format(_registro(usuario_id="u-1", duracao_ms=12.5))

    dados = json.loads(linha)
    assert dados["usuario_id"] == "u-1"
    assert dados["duracao_ms"] == 12.5


def test_formatador_json_serializa_valores_nao_json_como_texto():
    class Qualquer:
        def __str__(self):
            return "qualquer"

    dados = json.loads(FormatadorJson().format(_registro(objeto=Qualquer())))

    assert dados["objeto"] == "qualquer"


def test_formatador_json_inclui_a_excecao():
    try:
        raise ValueError("quebrou")
    except ValueError:
        registro = _registro(nivel=logging.ERROR)
        registro.exc_info = sys.exc_info()

    dados = json.loads(FormatadorJson().format(registro))

    assert "ValueError: quebrou" in dados["excecao"]


def test_formatador_json_aplica_os_argumentos_da_mensagem():
    registro = _registro("Ativo %s falhou")
    registro.args = ("PETR4",)

    assert json.loads(FormatadorJson().format(registro))["mensagem"] == "Ativo PETR4 falhou"


def test_sem_correlacao_o_id_e_nulo():
    dados = json.loads(FormatadorJson().format(_registro()))

    assert dados["correlation_id"] is None


def test_formatador_texto_mostra_o_id_e_os_extras():
    with em_correlacao("abc123"):
        linha = FormatadorTexto().format(_registro("Requisicao.", status=200))

    assert "abc123" in linha
    assert "Requisicao." in linha
    assert "status=200" in linha


def test_em_correlacao_restaura_o_id_anterior():
    with em_correlacao("externo"):
        with em_correlacao("interno"):
            assert correlation_id_atual() == "interno"
        assert correlation_id_atual() == "externo"
    assert correlation_id_atual() is None


def test_em_correlacao_sem_id_gera_um_novo():
    with em_correlacao() as gerado:
        assert correlation_id_atual() == gerado
        assert id_de_correlacao_valido(gerado)


def test_correlacao_nao_vaza_entre_threads():
    vistos = []

    def outra_thread():
        vistos.append(correlation_id_atual())

    with em_correlacao("principal"):
        thread = threading.Thread(target=outra_thread)
        thread.start()
        thread.join()

    assert vistos == [None]


@pytest.mark.parametrize(
    ("valor", "valido"),
    [
        ("abc-123_x.y", True),
        ("a" * 64, True),
        ("a" * 65, False),
        ("", False),
        ("com espaco", False),
        ("quebra\nlinha", False),
    ],
)
def test_validacao_do_id_de_correlacao(valor, valido):
    assert id_de_correlacao_valido(valor) is valido


def test_configurar_logs_em_json_emite_no_handler_raiz(capsys):
    configurar_logs("INFO", "json")

    logging.getLogger("app.qualquer").info("Ola.", extra={"campo": 1})

    linha = capsys.readouterr().out.strip().splitlines()[-1]
    dados = json.loads(linha)
    assert dados["mensagem"] == "Ola."
    assert dados["campo"] == 1


def test_configurar_logs_desliga_o_access_log_do_uvicorn():
    configurar_logs("INFO", "json")

    assert logging.getLogger("uvicorn.access").disabled is True
    assert logging.getLogger("uvicorn.error").propagate is True


def test_configurar_logs_rejeita_formato_desconhecido():
    with pytest.raises(ValueError):
        configurar_logs("INFO", "xml")


def test_configurar_logs_silencia_bibliotecas_ruidosas():
    configurar_logs("INFO", "json")

    for nome in ("httpx", "httpcore", "apscheduler"):
        assert logging.getLogger(nome).level == logging.WARNING
