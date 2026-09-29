from __future__ import annotations

import logging
from uuid import UUID

from app.ai.contexto import serializar
from app.ai.providers.base import ChamadaFerramenta, DeclaracaoFerramenta, ResultadoFerramenta
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.services.exceptions import PortfolioVazioError
from app.services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

_MAX_OPERACOES = 100

_DECLARACOES = [
    DeclaracaoFerramenta(
        nome="obter_posicoes",
        descricao=(
            "Lista as posicoes atuais da carteira do usuario, com quantidade, preco medio, "
            "cotacao atual e lucros."
        ),
    ),
    DeclaracaoFerramenta(
        nome="obter_rentabilidade",
        descricao=(
            "Retorna a rentabilidade consolidada da carteira em BRL: custo base, valor de "
            "mercado, lucros e percentual (fracao decimal)."
        ),
    ),
    DeclaracaoFerramenta(
        nome="obter_distribuicao",
        descricao=(
            "Retorna a distribuicao da carteira por classe de ativo, setor e moeda, como "
            "fracoes decimais do total."
        ),
    ),
    DeclaracaoFerramenta(
        nome="listar_operacoes",
        descricao=(
            f"Lista as operacoes de compra e venda registradas pelo usuario "
            f"(as {_MAX_OPERACOES} mais recentes)."
        ),
    ),
    DeclaracaoFerramenta(
        nome="comparar_benchmark",
        descricao="Compara a rentabilidade da carteira com um benchmark (CDI ou IBOVESPA).",
        parametros={
            "type": "object",
            "properties": {
                "benchmark": {"type": "string", "enum": [b.value for b in TipoBenchmark]}
            },
            "required": ["benchmark"],
        },
    ),
]


class ExecutorFerramentas:
    def __init__(self, portfolio_service: PortfolioService, ativo_repository: AtivoRepository):
        self._portfolio_service = portfolio_service
        self._ativo_repository = ativo_repository

    def declaracoes(self) -> list[DeclaracaoFerramenta]:
        return list(_DECLARACOES)

    def executar(self, usuario_id: UUID, chamada: ChamadaFerramenta) -> ResultadoFerramenta:
        try:
            conteudo = self._despachar(usuario_id, chamada)
        except Exception:
            logger.warning("Falha ao executar a ferramenta %s.", chamada.nome, exc_info=True)
            conteudo = {"erro": "dado indisponivel"}
        return ResultadoFerramenta(nome=chamada.nome, conteudo=conteudo)

    def _despachar(self, usuario_id: UUID, chamada: ChamadaFerramenta) -> dict:
        if chamada.nome == "obter_posicoes":
            return {"posicoes": serializar(self._portfolio_service.posicoes(usuario_id))}
        if chamada.nome == "obter_rentabilidade":
            return serializar(self._portfolio_service.rentabilidade(usuario_id))
        if chamada.nome == "obter_distribuicao":
            return serializar(self._portfolio_service.distribuicao(usuario_id))
        if chamada.nome == "listar_operacoes":
            operacoes = sorted(
                self._portfolio_service.listar_operacoes(usuario_id),
                key=lambda operacao: (operacao.data, operacao.criado_em),
                reverse=True,
            )
            return {
                "operacoes": [self._descrever_operacao(op) for op in operacoes[:_MAX_OPERACOES]]
            }
        if chamada.nome == "comparar_benchmark":
            return self._comparar_benchmark(usuario_id, chamada.argumentos)
        return {"erro": f"ferramenta desconhecida: {chamada.nome}"}

    def _descrever_operacao(self, operacao) -> dict:
        ativo = self._ativo_repository.buscar_por_id(operacao.ativo_id)
        return serializar(
            {
                "ticker": ativo.ticker if ativo is not None else None,
                "tipo": operacao.tipo,
                "quantidade": operacao.quantidade,
                "preco_unitario": operacao.preco_unitario,
                "data": operacao.data,
            }
        )

    def _comparar_benchmark(self, usuario_id: UUID, argumentos: dict) -> dict:
        try:
            benchmark = TipoBenchmark(argumentos.get("benchmark"))
        except ValueError:
            return {"erro": "benchmark deve ser CDI ou IBOVESPA"}

        try:
            comparativo = self._portfolio_service.comparativo_benchmark(usuario_id, benchmark)
        except PortfolioVazioError:
            return {"erro": "nenhuma operacao registrada"}
        return serializar(comparativo)
