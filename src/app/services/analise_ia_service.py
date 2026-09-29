from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.ai.contexto import calcular_hash
from app.ai.guardrails.aplicar import gerar_com_guardrail
from app.ai.prompts.analise_ativo import PROMPT_VERSAO_ANALISE, montar_prompt_analise
from app.ai.providers.base import ProvedorLLM
from app.domain.entities.analise_ia import AnaliseIA
from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.entities.sinal import Sinal
from app.domain.regras_sinal_padrao import buscar_regra_por_id
from app.repositories.interfaces.analise_ia_repository import AnaliseIARepository
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.services.exceptions import AtivoNaoEncontradoError, ContextoInsuficienteError
from app.services.indicador_service import IndicadorService
from app.services.sinal_service import SinalService

_CASAS_INDICADOR = Decimal("0.0001")
_CASAS_VARIACAO = Decimal("0.01")


@dataclass
class ResultadoAnalise:
    analise: AnaliseIA
    em_cache: bool


class AnaliseIAService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        cotacao_repository: CotacaoRepository,
        indicador_service: IndicadorService,
        sinal_service: SinalService,
        analise_repository: AnaliseIARepository,
        provedor: ProvedorLLM,
    ):
        self._ativo_repository = ativo_repository
        self._cotacao_repository = cotacao_repository
        self._indicador_service = indicador_service
        self._sinal_service = sinal_service
        self._analise_repository = analise_repository
        self._provedor = provedor

    def analisar_ativo(self, ativo_id: UUID) -> ResultadoAnalise:
        ativo = self._buscar_ativo(ativo_id)
        contexto = self._montar_contexto(ativo)
        contexto_hash = calcular_hash(contexto)

        ultima = self._analise_repository.buscar_ultima_por_ativo(ativo.id)
        if (
            ultima is not None
            and ultima.contexto_hash == contexto_hash
            and ultima.prompt_versao == PROMPT_VERSAO_ANALISE
            and ultima.modelo == self._provedor.modelo
        ):
            return ResultadoAnalise(analise=ultima, em_cache=True)

        system, prompt = montar_prompt_analise(contexto)
        texto = gerar_com_guardrail(lambda s: self._provedor.gerar_texto(s, prompt), system)
        analise = AnaliseIA(
            id=uuid4(),
            ativo_id=ativo.id,
            texto=texto,
            provedor=self._provedor.nome,
            modelo=self._provedor.modelo,
            prompt_versao=PROMPT_VERSAO_ANALISE,
            contexto_hash=contexto_hash,
            gerado_em=datetime.now(UTC),
        )
        self._analise_repository.salvar(analise)
        return ResultadoAnalise(analise=analise, em_cache=False)

    def _montar_contexto(self, ativo: Ativo) -> dict:
        cotacoes = self._cotacao_repository.listar_por_ativo(ativo.id)
        indicadores = self._indicador_service.calcular_todos(ativo.id)
        if not cotacoes or not indicadores:
            raise ContextoInsuficienteError(ativo.id)

        sinais = self._sinal_service.avaliar_ativo(ativo.id)
        return {
            "ticker": ativo.ticker,
            "nome": ativo.nome,
            "tipo": ativo.tipo,
            "cotacao": _resumir_cotacao(cotacoes),
            "indicadores": _resumir_indicadores(indicadores),
            "sinais": _resumir_sinais(sinais),
            "score_composto": self._sinal_service.score_composto(ativo.id),
        }

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo


def _resumir_cotacao(cotacoes: list[Cotacao]) -> dict:
    ultima = cotacoes[-1]
    variacao = None
    if len(cotacoes) > 1 and cotacoes[-2].fechamento != 0:
        anterior = cotacoes[-2].fechamento
        variacao = ((ultima.fechamento - anterior) / anterior * 100).quantize(_CASAS_VARIACAO)
    return {
        "fechamento": ultima.fechamento,
        "data": ultima.data_hora,
        "variacao_percentual": variacao,
    }


def _resumir_indicadores(indicadores: list[IndicadorTecnico]) -> list[dict]:
    ordenados = sorted(
        indicadores,
        key=lambda i: (i.tipo.value, json.dumps(i.parametros, sort_keys=True)),
    )
    return [
        {
            "tipo": indicador.tipo,
            "parametros": indicador.parametros,
            "valor": indicador.valor.quantize(_CASAS_INDICADOR),
            "valores_auxiliares": _arredondar(indicador.valores_auxiliares),
        }
        for indicador in ordenados
    ]


def _arredondar(auxiliares: dict | None) -> dict | None:
    if auxiliares is None:
        return None
    return {chave: round(valor, 4) for chave, valor in auxiliares.items()}


def _resumir_sinais(sinais: list[Sinal]) -> list[dict]:
    resumo = []
    for sinal in sinais:
        regra = buscar_regra_por_id(sinal.regra_id)
        if regra is not None:
            resumo.append({"regra": regra.nome, "descricao": regra.descricao})
    return sorted(resumo, key=lambda item: item["regra"])
