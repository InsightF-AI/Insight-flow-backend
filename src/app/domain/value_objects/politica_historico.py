from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo


@dataclass(frozen=True)
class PoliticaHistorico:
    periodo_backfill: PeriodoHistorico
    periodo_backfill_cripto: PeriodoHistorico
    minimo_cotacoes: int

    def periodo_backfill_de(self, tipo: TipoAtivo) -> PeriodoHistorico:
        if tipo == TipoAtivo.CRIPTO:
            return self.periodo_backfill_cripto
        return self.periodo_backfill
