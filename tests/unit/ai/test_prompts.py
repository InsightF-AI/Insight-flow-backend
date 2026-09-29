from app.ai.prompts.analise_ativo import PROMPT_VERSAO_ANALISE, montar_prompt_analise
from app.ai.prompts.chat import PROMPT_VERSAO_CHAT, SYSTEM_PROMPT_CHAT
from app.ai.prompts.resumo_diario import PROMPT_VERSAO_RESUMO, montar_prompt_resumo


def test_prompt_de_analise_leva_os_dados_e_as_regras_de_grounding():
    system, prompt = montar_prompt_analise({"ticker": "PETR4", "score_composto": "1.0"})

    assert "PETR4" in prompt
    assert "DADOS" in prompt
    assert "exclusivamente" in system
    assert "comprar" in system
    assert "vender" in system


def test_prompt_de_resumo_declara_que_percentuais_sao_fracao_decimal():
    system, prompt = montar_prompt_resumo({"rentabilidade": {"percentual": "0.05"}})

    assert "fração decimal" in system
    assert "0.05 equivale a 5%" in system
    assert "0.05" in prompt


def test_system_do_chat_declara_fracao_decimal_e_proibe_recomendacao():
    assert "fração decimal" in SYSTEM_PROMPT_CHAT
    assert "comprar" in SYSTEM_PROMPT_CHAT
    assert "ferramentas" in SYSTEM_PROMPT_CHAT


def test_system_do_chat_manda_recusar_pedido_de_recomendacao_sem_palavras_proibidas():
    assert "não emite recomendações de investimento" in SYSTEM_PROMPT_CHAT


def test_versoes_de_prompt_sao_distintas_e_estaveis():
    assert PROMPT_VERSAO_ANALISE == "analise_ativo.v1"
    assert PROMPT_VERSAO_RESUMO == "resumo_diario.v1"
    assert PROMPT_VERSAO_CHAT == "chat.v1"
