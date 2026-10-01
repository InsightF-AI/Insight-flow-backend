import pytest

from app.ai.guardrails.aplicar import gerar_com_guardrail
from app.services.exceptions import RespostaViolaGuardrailError


class _Produtor:
    def __init__(self, textos: list[str]):
        self._textos = list(textos)
        self.systems: list[str] = []

    def __call__(self, system: str) -> str:
        self.systems.append(system)
        return self._textos.pop(0)


def test_texto_limpo_passa_sem_regenerar():
    produtor = _Produtor(["O RSI indica condição neutra."])

    texto = gerar_com_guardrail(produtor, "SYSTEM")

    assert texto == "O RSI indica condição neutra."
    assert produtor.systems == ["SYSTEM"]


def test_violacao_regenera_uma_vez_com_system_reforcado():
    produtor = _Produtor(["Compre agora.", "O RSI indica condição neutra."])

    texto = gerar_com_guardrail(produtor, "SYSTEM")

    assert texto == "O RSI indica condição neutra."
    assert len(produtor.systems) == 2
    assert produtor.systems[0] == "SYSTEM"
    assert produtor.systems[1].startswith("SYSTEM")
    assert '"compre"' in produtor.systems[1]


def test_segunda_violacao_levanta_erro():
    produtor = _Produtor(["Compre agora.", "Venda tudo."])

    with pytest.raises(RespostaViolaGuardrailError):
        gerar_com_guardrail(produtor, "SYSTEM")

    assert len(produtor.systems) == 2
