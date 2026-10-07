import threading

import pytest

from app.integrations.limitador import LimitadorTaxa, LimiteTaxaExcedidoError


class _Relogio:
    def __init__(self):
        self.agora = 0.0
        self.esperas: list[float] = []

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.agora += segundos


def _limitador(relogio: _Relogio, por_minuto: int = 60, espera_maxima: float = 10.0):
    return LimitadorTaxa(
        requisicoes_por_minuto=por_minuto,
        espera_maxima_segundos=espera_maxima,
        relogio=relogio,
        dormir=relogio.dormir,
    )


def test_libera_sem_esperar_enquanto_ha_capacidade():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=3)

    for _ in range(3):
        limitador.adquirir()

    assert relogio.esperas == []


def test_espera_o_intervalo_de_uma_ficha_quando_a_capacidade_acaba():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=60)
    for _ in range(60):
        limitador.adquirir()

    limitador.adquirir()

    assert relogio.esperas == [pytest.approx(1.0)]


def test_requisicoes_em_fila_esperam_cada_uma_a_sua_vez():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=60)
    for _ in range(60):
        limitador.adquirir()

    limitador.adquirir()
    limitador.adquirir()

    assert relogio.esperas == [pytest.approx(1.0), pytest.approx(1.0)]


def test_repoe_fichas_com_o_tempo():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=60)
    for _ in range(60):
        limitador.adquirir()

    relogio.agora += 5.0
    for _ in range(5):
        limitador.adquirir()

    assert relogio.esperas == []


def test_nao_acumula_fichas_alem_da_capacidade():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=2, espera_maxima=60.0)

    relogio.agora += 3600.0
    for _ in range(3):
        limitador.adquirir()

    assert relogio.esperas == [pytest.approx(30.0)]


def test_lanca_erro_quando_a_espera_passaria_do_teto():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=6, espera_maxima=5.0)
    for _ in range(6):
        limitador.adquirir()

    with pytest.raises(LimiteTaxaExcedidoError):
        limitador.adquirir()

    assert relogio.esperas == []


def test_espera_recusada_nao_consome_ficha():
    relogio = _Relogio()
    limitador = _limitador(relogio, por_minuto=6, espera_maxima=5.0)
    for _ in range(6):
        limitador.adquirir()
    with pytest.raises(LimiteTaxaExcedidoError):
        limitador.adquirir()

    relogio.agora += 10.0
    limitador.adquirir()

    assert relogio.esperas == []


def test_taxa_invalida_lanca_erro():
    with pytest.raises(ValueError):
        LimitadorTaxa(requisicoes_por_minuto=0, espera_maxima_segundos=1.0)


def test_entre_threads_nao_libera_mais_fichas_que_a_capacidade():
    limitador = LimitadorTaxa(requisicoes_por_minuto=60, espera_maxima_segundos=0.5)
    liberadas: list[int] = []
    recusadas: list[int] = []
    trava = threading.Lock()

    def consumir():
        for _ in range(20):
            try:
                limitador.adquirir()
            except LimiteTaxaExcedidoError:
                with trava:
                    recusadas.append(1)
            else:
                with trava:
                    liberadas.append(1)

    threads = [threading.Thread(target=consumir) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(liberadas) + len(recusadas) == 100
    assert len(recusadas) > 0
    assert len(liberadas) <= 61
