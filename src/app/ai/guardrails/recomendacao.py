from __future__ import annotations

import re
import unicodedata

_VERBOS = r"(?:comprar|vender|investir|aportar|resgatar|acumular|liquidar)"
_VERBOS_ACAO = r"(?:comprar|vender|investir|aportar|resgatar|acumular|liquidar|aproveitar|reduzir|aumentar|manter|diversificar)"

_PADROES = [
    re.compile(padrao, re.MULTILINE)
    for padrao in (
        r"\b(?:compre|comprem|invista|investam|aproveite|acumule|liquide|zere)\b",
        r"\b(?:mantenha|reduza|aumente|diversifique)\b",
        r"(?:^|[.!?;:,]\s*)(?:venda|vendam|aproveitar)\b(?!\s+(?:de|do|da|dos|das|no|na|em|por|e|ou)\b)",
        r"\brecomendacao\s*(?::|e\b)",
        r"\brealize\s+(?:o\s+)?lucros?\b",
        r"\bmonte\s+(?:uma\s+)?posicao\b",
        r"\b(?:recomendo|recomendamos|sugiro|sugerimos|aconselho|recomenda-se|sugere-se)\b",
        rf"\bvoce\s+(?:deve|deveria|precisa)\s+{_VERBOS}\b",
        rf"\b(?:deve|deveria|devem)\s+{_VERBOS}\b",
        rf"\b(?:e\s+hora\s+de|vale\s+a\s+pena|(?:bom|melhor)\s+momento\s+para|considere)\s+{_VERBOS_ACAO}\b",
        rf"\bideal\s+(?:e|seria)\s+{_VERBOS_ACAO}\b",
    )
]


def _normalizar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def encontrar_violacoes(texto: str) -> list[str]:
    normalizado = _normalizar(texto)
    encontrados: list[str] = []
    for padrao in _PADROES:
        for ocorrencia in padrao.finditer(normalizado):
            trecho = ocorrencia.group(0).strip(" .!?;:\n")
            if trecho not in encontrados:
                encontrados.append(trecho)
    return encontrados


def montar_reforco(violacoes: list[str]) -> str:
    termos = "; ".join(f'"{violacao}"' for violacao in violacoes)
    return (
        "\n\nATENCAO: a resposta anterior foi rejeitada por conter linguagem de recomendacao "
        f"de investimento ({termos}). Reescreva descrevendo apenas condicoes tecnicas "
        "detectadas, de forma factual, sem verbos imperativos e sem sugerir nenhuma acao."
    )
