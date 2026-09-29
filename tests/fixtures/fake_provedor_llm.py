from __future__ import annotations

from app.ai.providers.base import (
    DeclaracaoFerramenta,
    MensagemChat,
    ProvedorLLM,
    RespostaLLM,
)


class FakeProvedorLLM(ProvedorLLM):
    nome = "fake"

    def __init__(self, respostas: list | None = None, modelo: str = "fake-1") -> None:
        self.modelo = modelo
        self._respostas: list = list(respostas or [])
        self.chamadas_gerar: list[tuple[str, str]] = []
        self.chamadas_conversar: list[
            tuple[str, list[MensagemChat], list[DeclaracaoFerramenta]]
        ] = []

    def enfileirar(self, *respostas) -> None:
        self._respostas.extend(respostas)

    def gerar_texto(self, system: str, prompt: str) -> str:
        self.chamadas_gerar.append((system, prompt))
        item = self._proxima()
        return item.texto if isinstance(item, RespostaLLM) else item

    def conversar(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> RespostaLLM:
        self.chamadas_conversar.append((system, list(mensagens), list(ferramentas)))
        item = self._proxima()
        return item if isinstance(item, RespostaLLM) else RespostaLLM(texto=item)

    def _proxima(self):
        if not self._respostas:
            raise AssertionError("FakeProvedorLLM sem resposta enfileirada")
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
