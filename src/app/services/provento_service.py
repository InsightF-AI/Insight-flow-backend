from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.provento import Provento, ProventoRecebido, ResumoProventos
from app.integrations.erros import TickerNaoEncontradoError
from app.integrations.yahoo.client import YahooFinanceClient
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.mercado_cache import MercadoCache
from app.services.portfolio_service import replay_operacoes

_TIPOS_SEM_PROVENTOS = (TipoAtivo.CRIPTO, TipoAtivo.INDICE)


class ProventoService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        operacao_repository: OperacaoRepository,
        fonte: YahooFinanceClient,
        cache: MercadoCache,
        ttl_segundos: int,
    ):
        self._ativo_repository = ativo_repository
        self._operacao_repository = operacao_repository
        self._fonte = fonte
        self._cache = cache
        self._ttl_segundos = ttl_segundos

    def historico(self, ativo_id: UUID) -> list[Provento]:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return self._proventos(ativo)

    def recebidos(self, usuario_id: UUID) -> ResumoProventos:
        operacoes = self._operacao_repository.listar_por_usuario(usuario_id)
        por_ativo: dict[UUID, list] = {}
        for operacao in operacoes:
            por_ativo.setdefault(operacao.ativo_id, []).append(operacao)

        recebidos: list[ProventoRecebido] = []
        for ativo_id, operacoes_ativo in por_ativo.items():
            ativo = self._ativo_repository.buscar_por_id(ativo_id)
            if ativo is None:
                continue
            for provento in self._proventos(ativo):
                anteriores = [op for op in operacoes_ativo if op.data < provento.data_ex]
                quantidade = replay_operacoes(anteriores).quantidade
                if quantidade > 0:
                    recebidos.append(
                        ProventoRecebido(
                            ativo_id=ativo.id,
                            ticker=ativo.ticker,
                            data_ex=provento.data_ex,
                            valor_por_cota=provento.valor_por_cota,
                            quantidade=quantidade,
                            total_brl=provento.valor_por_cota * quantidade,
                        )
                    )

        recebidos.sort(key=lambda item: (item.data_ex, item.ticker), reverse=True)
        total = sum((item.total_brl for item in recebidos), Decimal(0))
        return ResumoProventos(total_brl=total, proventos=recebidos)

    def _proventos(self, ativo: Ativo) -> list[Provento]:
        if ativo.tipo in _TIPOS_SEM_PROVENTOS:
            return []

        chave = f"proventos:{ativo.ticker}"
        em_cache = self._cache.obter(chave)
        if em_cache is not None:
            return [
                Provento(data_ex=date.fromisoformat(item[0]), valor_por_cota=Decimal(item[1]))
                for item in json.loads(em_cache)
            ]

        try:
            proventos = self._fonte.buscar_proventos(ativo.ticker)
        except TickerNaoEncontradoError:
            proventos = []
        self._cache.salvar(
            chave,
            json.dumps([[p.data_ex.isoformat(), str(p.valor_por_cota)] for p in proventos]),
            self._ttl_segundos,
        )
        return proventos
