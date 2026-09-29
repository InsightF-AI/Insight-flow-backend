from uuid import uuid4

from app.integrations.bcb.client import BcbIndisponivelError
from app.scheduler.resumo_diario import gerar_resumos_diarios
from app.services.exceptions import (
    LLMCotaExcedidaError,
    LLMIndisponivelError,
    RespostaViolaGuardrailError,
)
from tests.fixtures.cenario_portfolio import ATIVO_PETR4, nova_operacao
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository


class _ResumoServiceFalso:
    def __init__(self, comportamentos: dict):
        self._comportamentos = comportamentos
        self.chamados: list = []

    def gerar(self, usuario_id):
        self.chamados.append(usuario_id)
        comportamento = self._comportamentos.get(usuario_id)
        if isinstance(comportamento, Exception):
            raise comportamento
        return comportamento


def _repositorio_com(*usuarios):
    repositorio = FakeOperacaoRepository()
    for usuario_id in usuarios:
        repositorio.salvar(nova_operacao(usuario_id, ATIVO_PETR4.id))
    return repositorio


def test_gera_para_todos_os_usuarios_com_operacoes_e_pausa_apos_cada_geracao():
    a, b = uuid4(), uuid4()
    service = _ResumoServiceFalso({a: object(), b: object()})
    esperas: list = []

    gerar_resumos_diarios(_repositorio_com(a, b), service, 6, dormir=esperas.append)

    assert service.chamados == [a, b]
    assert esperas == [6, 6]


def test_nao_pausa_quando_o_usuario_foi_pulado():
    a, b = uuid4(), uuid4()
    service = _ResumoServiceFalso({a: None, b: object()})
    esperas: list = []

    gerar_resumos_diarios(_repositorio_com(a, b), service, 6, dormir=esperas.append)

    assert service.chamados == [a, b]
    assert esperas == [6]


def test_falha_de_um_usuario_nao_interrompe_o_lote():
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    service = _ResumoServiceFalso(
        {
            a: LLMIndisponivelError(),
            b: RespostaViolaGuardrailError(),
            c: BcbIndisponivelError(),
            d: object(),
        }
    )
    falhas: list = []

    gerar_resumos_diarios(
        _repositorio_com(a, b, c, d),
        service,
        0,
        dormir=lambda _: None,
        ao_falhar_usuario=lambda: falhas.append(1),
    )

    assert service.chamados == [a, b, c, d]
    assert len(falhas) == 3


def test_cota_excedida_interrompe_o_lote_inteiro():
    a, b, c = uuid4(), uuid4(), uuid4()
    service = _ResumoServiceFalso({a: object(), b: LLMCotaExcedidaError(), c: object()})

    gerar_resumos_diarios(_repositorio_com(a, b, c), service, 0, dormir=lambda _: None)

    assert service.chamados == [a, b]


def test_sem_usuarios_com_operacoes_nao_faz_nada():
    service = _ResumoServiceFalso({})

    gerar_resumos_diarios(FakeOperacaoRepository(), service, 6, dormir=lambda _: None)

    assert service.chamados == []
