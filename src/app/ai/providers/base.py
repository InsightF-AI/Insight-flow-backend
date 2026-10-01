from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class PapelMensagem(str, Enum):
    USUARIO = "usuario"
    ASSISTENTE = "assistente"


@dataclass(frozen=True)
class ChamadaFerramenta:
    nome: str
    argumentos: dict
    assinatura: str | None = None


@dataclass(frozen=True)
class ResultadoFerramenta:
    nome: str
    conteudo: dict


@dataclass(frozen=True)
class MensagemChat:
    papel: PapelMensagem
    texto: str = ""
    chamadas: tuple[ChamadaFerramenta, ...] = field(default_factory=tuple)
    resultados: tuple[ResultadoFerramenta, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DeclaracaoFerramenta:
    nome: str
    descricao: str
    parametros: dict | None = None


@dataclass(frozen=True)
class RespostaLLM:
    texto: str = ""
    chamadas: tuple[ChamadaFerramenta, ...] = field(default_factory=tuple)


class ProvedorLLM(ABC):
    nome: str
    modelo: str

    @abstractmethod
    def gerar_texto(self, system: str, prompt: str) -> str: ...

    @abstractmethod
    def conversar(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> RespostaLLM: ...
