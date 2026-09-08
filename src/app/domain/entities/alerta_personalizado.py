from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta


@dataclass
class AlertaPersonalizado:
    id: UUID
    usuario_id: UUID
    ativo_id: UUID
    tipo_condicao: TipoCondicaoAlerta
    valor_alvo: Decimal
    criado_em: datetime
    atualizado_em: datetime
    ativo: bool = True
    ultimo_estado: bool = False
    disparado_em: datetime | None = None

    @staticmethod
    def criar(
        id: UUID,
        usuario_id: UUID,
        ativo_id: UUID,
        tipo_condicao: TipoCondicaoAlerta,
        valor_alvo: Decimal,
        criado_em: datetime,
    ) -> AlertaPersonalizado:
        if valor_alvo <= 0:
            raise ValueError("valor_alvo deve ser maior que zero")
        return AlertaPersonalizado(
            id=id,
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            tipo_condicao=tipo_condicao,
            valor_alvo=valor_alvo,
            criado_em=criado_em,
            atualizado_em=criado_em,
        )

    def avaliar(self, preco_atual: Decimal, agora: datetime) -> bool:
        if not self.ativo:
            return False

        if not self._condicao_satisfeita(preco_atual):
            self.ultimo_estado = False
            return False

        disparou = not self.ultimo_estado
        self.ultimo_estado = True
        if disparou:
            self.disparado_em = agora
        return disparou

    def _condicao_satisfeita(self, preco_atual: Decimal) -> bool:
        if self.tipo_condicao == TipoCondicaoAlerta.PRECO_MAIOR_IGUAL:
            return preco_atual >= self.valor_alvo
        return preco_atual <= self.valor_alvo

    def rearmar(self) -> None:
        self.ultimo_estado = False
