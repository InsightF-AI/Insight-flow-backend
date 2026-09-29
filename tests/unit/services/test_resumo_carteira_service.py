from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.services.exceptions import LLMCotaExcedidaError, RespostaViolaGuardrailError
from app.services.notificacao_service import NotificacaoService
from app.services.resumo_carteira_service import ResumoCarteiraService
from tests.fixtures.cenario_portfolio import (
    ATIVO_PETR4,
    cotacao_atual,
    montar_portfolio_service,
    nova_operacao,
)
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_provedor_llm import FakeProvedorLLM


def _cenario(com_operacao: bool = True, agora=None):
    usuario_id = uuid4()
    operacoes = [nova_operacao(usuario_id, ATIVO_PETR4.id)] if com_operacao else []
    portfolio_service = montar_portfolio_service(
        [ATIVO_PETR4], operacoes, {"PETR4": cotacao_atual("PETR4", "35.00")}
    )
    repository = FakeNotificacaoRepository()
    provedor = FakeProvedorLLM()
    kwargs = {"agora": agora} if agora is not None else {}
    service = ResumoCarteiraService(
        NotificacaoService(repository), portfolio_service, provedor, **kwargs
    )
    return service, usuario_id, repository, provedor


def _resumo_existente(usuario_id, criado_em, texto):
    return Notificacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=None,
        tipo=TipoNotificacao.RESUMO_DIARIO,
        mensagem="Resumo diario da carteira",
        contexto={"texto": texto},
        criado_em=criado_em,
    )


def test_gerar_cria_notificacao_de_resumo_com_texto_e_aviso_legal():
    service, usuario_id, repository, provedor = _cenario()
    texto = "A carteira soma valor de mercado estavel. " * 60
    provedor.enfileirar(texto)

    notificacao = service.gerar(usuario_id)

    assert notificacao is not None
    assert notificacao.tipo == TipoNotificacao.RESUMO_DIARIO
    assert notificacao.ativo_id is None
    assert notificacao.mensagem == "Resumo diario da carteira"
    assert notificacao.contexto["texto"] == texto
    assert len(notificacao.contexto["texto"]) > 255
    assert notificacao.contexto["aviso_legal"].startswith("Análise gerada por IA")
    assert notificacao.contexto["modelo"] == "fake-1"
    assert notificacao.contexto["prompt_versao"] == "resumo_diario.v1"
    assert len(notificacao.contexto["contexto_hash"]) == 64
    assert repository.buscar_por_id(notificacao.id) == notificacao


def test_prompt_do_resumo_leva_as_posicoes_da_carteira():
    service, usuario_id, _, provedor = _cenario()
    provedor.enfileirar("Resumo neutro da carteira.")

    service.gerar(usuario_id)

    _, prompt = provedor.chamadas_gerar[0]
    assert "PETR4" in prompt
    assert "rentabilidade" in prompt
    assert "distribuicao" in prompt


def test_gerar_sem_posicoes_retorna_none_sem_chamar_a_llm():
    service, usuario_id, repository, provedor = _cenario(com_operacao=False)

    assert service.gerar(usuario_id) is None
    assert provedor.chamadas_gerar == []
    assert repository.listar_por_usuario(usuario_id) == []


def test_segunda_geracao_no_mesmo_dia_retorna_none_sem_chamar_a_llm():
    service, usuario_id, _, provedor = _cenario()
    provedor.enfileirar("Resumo do dia.")

    primeira = service.gerar(usuario_id)
    segunda = service.gerar(usuario_id)

    assert primeira is not None
    assert segunda is None
    assert len(provedor.chamadas_gerar) == 1


def test_gera_novamente_quando_o_resumo_anterior_e_de_outro_dia_em_sao_paulo():
    service, usuario_id, repository, provedor = _cenario(
        agora=lambda: datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )
    repository.salvar(
        _resumo_existente(usuario_id, datetime(2026, 9, 30, 1, 0, tzinfo=UTC), "de ontem")
    )
    provedor.enfileirar("Resumo de hoje.")

    notificacao = service.gerar(usuario_id)

    assert notificacao is not None
    assert notificacao.contexto["texto"] == "Resumo de hoje."


def test_nao_gera_quando_o_resumo_existente_e_do_mesmo_dia_em_sao_paulo():
    service, usuario_id, repository, provedor = _cenario(
        agora=lambda: datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    )
    repository.salvar(
        _resumo_existente(usuario_id, datetime(2026, 9, 30, 9, 0, tzinfo=UTC), "de hoje cedo")
    )

    assert service.gerar(usuario_id) is None
    assert provedor.chamadas_gerar == []


def test_duas_violacoes_levantam_erro_e_nao_criam_notificacao():
    service, usuario_id, repository, provedor = _cenario()
    provedor.enfileirar("Compre agora.", "Venda tudo.")

    with pytest.raises(RespostaViolaGuardrailError):
        service.gerar(usuario_id)

    assert repository.listar_por_usuario(usuario_id) == []


def test_cota_excedida_propaga_e_nao_cria_notificacao():
    service, usuario_id, repository, provedor = _cenario()
    provedor.enfileirar(LLMCotaExcedidaError(retry_after=10))

    with pytest.raises(LLMCotaExcedidaError):
        service.gerar(usuario_id)

    assert repository.listar_por_usuario(usuario_id) == []
