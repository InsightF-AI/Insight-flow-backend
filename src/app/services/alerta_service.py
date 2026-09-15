from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.repositories.interfaces.alerta_repository import AlertaRepository
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.services.cambio_service import CambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AlertaNaoEncontradoError, AtivoNaoEncontradoError


@dataclass
class ItemAlerta:
    alerta: AlertaPersonalizado
    ativo: Ativo


class AlertaService:
    def __init__(
        self,
        alerta_repository: AlertaRepository,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
        cambio_service: CambioService,
    ):
        self._alerta_repository = alerta_repository
        self._ativo_repository = ativo_repository
        self._dados_mercado_service = dados_mercado_service
        self._cambio_service = cambio_service

    def criar_alerta(
        self,
        usuario_id: UUID,
        ticker: str,
        tipo_condicao: TipoCondicaoAlerta,
        valor_alvo: Decimal,
    ) -> ItemAlerta:
        ticker = ticker.upper()
        ativo = self._ativo_repository.buscar_por_ticker(ticker)
        if ativo is None:
            ativo = self._resolver_ativo_na_brapi(ticker)
            self._ativo_repository.salvar(ativo)

        agora = datetime.now(UTC)
        alerta = AlertaPersonalizado.criar(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo.id,
            tipo_condicao=tipo_condicao,
            valor_alvo=valor_alvo,
            moeda_alvo=ativo.moeda,
            criado_em=agora,
        )
        self._alerta_repository.salvar(alerta)
        return ItemAlerta(alerta=alerta, ativo=ativo)

    def listar_alertas(self, usuario_id: UUID) -> list[ItemAlerta]:
        alertas = self._alerta_repository.listar_por_usuario(usuario_id)
        return [
            ItemAlerta(alerta=alerta, ativo=self._ativo_repository.buscar_por_id(alerta.ativo_id))
            for alerta in alertas
        ]

    def atualizar_alerta(
        self,
        usuario_id: UUID,
        alerta_id: UUID,
        tipo_condicao: TipoCondicaoAlerta | None = None,
        valor_alvo: Decimal | None = None,
        ativo: bool | None = None,
    ) -> ItemAlerta:
        alerta = self._buscar_alerta(usuario_id, alerta_id)

        precisa_rearmar = False
        if tipo_condicao is not None and tipo_condicao != alerta.tipo_condicao:
            alerta.tipo_condicao = tipo_condicao
            precisa_rearmar = True
        if valor_alvo is not None and valor_alvo != alerta.valor_alvo:
            if valor_alvo <= 0:
                raise ValueError("valor_alvo deve ser maior que zero")
            alerta.valor_alvo = valor_alvo
            precisa_rearmar = True
        if ativo is not None and ativo != alerta.ativo:
            if ativo and not alerta.ativo:
                precisa_rearmar = True
            alerta.ativo = ativo

        if precisa_rearmar:
            alerta.rearmar()

        alerta.atualizado_em = datetime.now(UTC)
        self._alerta_repository.salvar(alerta)
        ativo_entidade = self._ativo_repository.buscar_por_id(alerta.ativo_id)
        return ItemAlerta(alerta=alerta, ativo=ativo_entidade)

    def remover_alerta(self, usuario_id: UUID, alerta_id: UUID) -> None:
        alerta = self._buscar_alerta(usuario_id, alerta_id)
        self._alerta_repository.remover(alerta)

    def _buscar_alerta(self, usuario_id: UUID, alerta_id: UUID) -> AlertaPersonalizado:
        alerta = self._alerta_repository.buscar_por_id(alerta_id)
        if alerta is None or alerta.usuario_id != usuario_id:
            raise AlertaNaoEncontradoError(alerta_id)
        return alerta

    def _resolver_ativo_na_brapi(self, ticker: str) -> Ativo:
        encontrados = self._dados_mercado_service.buscar_ativo(ticker)
        correspondente = next((a for a in encontrados if a.ticker == ticker), None)
        if correspondente is None:
            raise AtivoNaoEncontradoError(ticker)

        return Ativo(
            id=uuid4(),
            ticker=correspondente.ticker,
            nome=correspondente.nome,
            tipo=correspondente.tipo,
            setor=correspondente.setor,
            moeda=correspondente.moeda,
            fonte_dados="brapi",
        )
