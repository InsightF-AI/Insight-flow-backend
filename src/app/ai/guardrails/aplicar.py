from __future__ import annotations

from collections.abc import Callable

from app.ai.guardrails.recomendacao import encontrar_violacoes, montar_reforco
from app.services.exceptions import RespostaViolaGuardrailError


def gerar_com_guardrail(produzir: Callable[[str], str], system: str) -> str:
    texto = produzir(system)
    violacoes = encontrar_violacoes(texto)
    if not violacoes:
        return texto

    texto = produzir(system + montar_reforco(violacoes))
    if encontrar_violacoes(texto):
        raise RespostaViolaGuardrailError
    return texto
