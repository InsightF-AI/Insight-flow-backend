from __future__ import annotations

import threading
import time
from collections.abc import Callable


class LimiteTaxaExcedidoError(Exception):
    def __init__(self, espera_segundos: float):
        super().__init__(f"Espera de {espera_segundos:.1f}s excede o teto do limitador")
        self.espera_segundos = espera_segundos


class LimitadorTaxa:
    def __init__(
        self,
        requisicoes_por_minuto: int,
        espera_maxima_segundos: float,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
    ):
        if requisicoes_por_minuto <= 0:
            raise ValueError("requisicoes_por_minuto deve ser maior que zero")
        self._capacidade = float(requisicoes_por_minuto)
        self._fichas_por_segundo = requisicoes_por_minuto / 60.0
        self._espera_maxima_segundos = espera_maxima_segundos
        self._relogio = relogio
        self._dormir = dormir
        self._fichas = self._capacidade
        self._atualizado_em = relogio()
        self._trava = threading.Lock()

    def adquirir(self) -> None:
        with self._trava:
            agora = self._relogio()
            self._repor(agora)
            espera = max(0.0, (1.0 - self._fichas) / self._fichas_por_segundo)
            if espera > self._espera_maxima_segundos:
                raise LimiteTaxaExcedidoError(espera)
            self._fichas -= 1.0
        if espera > 0:
            self._dormir(espera)

    def _repor(self, agora: float) -> None:
        decorrido = agora - self._atualizado_em
        self._fichas = min(self._capacidade, self._fichas + decorrido * self._fichas_por_segundo)
        self._atualizado_em = agora
