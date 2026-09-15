from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.services.alerta_service import ItemAlerta


class CriarAlertaRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    tipo_condicao: TipoCondicaoAlerta
    valor_alvo: Decimal = Field(gt=0)


class AtualizarAlertaRequest(BaseModel):
    tipo_condicao: TipoCondicaoAlerta | None = None
    valor_alvo: Decimal | None = Field(default=None, gt=0)
    ativo: bool | None = None


class AtivoResumoResponse(BaseModel):
    id: UUID
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    moeda: str


class AlertaResponse(BaseModel):
    id: UUID
    ativo: AtivoResumoResponse
    tipo_condicao: TipoCondicaoAlerta
    valor_alvo: Decimal
    moeda_alvo: str
    habilitado: bool
    ultimo_estado: bool
    disparado_em: datetime | None
    criado_em: datetime
    atualizado_em: datetime

    @staticmethod
    def de(item: ItemAlerta) -> "AlertaResponse":
        return AlertaResponse(
            id=item.alerta.id,
            ativo=AtivoResumoResponse(
                id=item.ativo.id,
                ticker=item.ativo.ticker,
                nome=item.ativo.nome,
                tipo=item.ativo.tipo,
                setor=item.ativo.setor,
                moeda=item.ativo.moeda,
            ),
            tipo_condicao=item.alerta.tipo_condicao,
            valor_alvo=item.alerta.valor_alvo,
            moeda_alvo=item.alerta.moeda_alvo,
            habilitado=item.alerta.ativo,
            ultimo_estado=item.alerta.ultimo_estado,
            disparado_em=item.alerta.disparado_em,
            criado_em=item.alerta.criado_em,
            atualizado_em=item.alerta.atualizado_em,
        )
