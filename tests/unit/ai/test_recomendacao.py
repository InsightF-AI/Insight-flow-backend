import pytest

from app.ai.guardrails.aviso_legal import AVISO_LEGAL
from app.ai.guardrails.recomendacao import encontrar_violacoes, montar_reforco


def test_aviso_legal_tem_o_texto_exato_da_rn_05():
    assert AVISO_LEGAL == "Análise gerada por IA. Não constitui recomendação de investimento."


@pytest.mark.parametrize(
    "texto",
    [
        "Compre PETR4 agora.",
        "Recomendo cautela nesta alta.",
        "É hora de vender ativos de risco.",
        "Você deve investir mais neste ativo.",
        "Vale a pena comprar na queda.",
        "Venda PETR4 imediatamente.",
        "O RSI está alto. Venda imediatamente.",
        "Considere aportar mais.",
        "Realize lucro nesta alta.",
        "Aproveite a queda.",
        "Monte uma posição agora.",
        "Recomenda-se reduzir a exposição.",
        "O investidor deve comprar na correção.",
        "Nossa recomendação é comprar PETR4.",
        "Recomendação: compra.",
        "Diante disso, venda PETR4.",
        "Mantenha a posição.",
        "É um bom momento para comprar.",
        "O ideal seria vender.",
        "Reduza a posição.",
        "Considere reduzir a exposição.",
        "Aproveitar a queda para entrar.",
        "Você precisa comprar mais.",
    ],
)
def test_texto_com_recomendacao_e_detectado(texto):
    assert encontrar_violacoes(texto) != []


@pytest.mark.parametrize(
    "texto",
    [
        "O RSI de 28 indica condição de sobrevenda.",
        "Há pressão vendedora e volume de compra acima da média.",
        "Venda de ativos do setor cresceu no período.",
        "O ativo negocia acima da média móvel de 20 períodos.",
        "O fundo registrou resgate de cotas no período.",
        "O sinal de compra do MACD foi detectado.",
        "Investidores devem observar o histórico de volatilidade.",
        "A ordem de compra e venda foi executada.",
        "Condição técnica de sobrecompra detectada pelo RSI(14).",
        "O sistema não emite recomendações de investimento. Sua posição em PETR4 é de 10 cotas.",
        "Você precisa cadastrar operações para que eu veja sua carteira.",
        "O preço deve manter a tendência de alta no curto prazo.",
        "Volume de compra, venda e manutenção de ordens ficou estável.",
        "Não constitui recomendação de investimento.",
    ],
)
def test_texto_descritivo_neutro_nao_e_detectado(texto):
    assert encontrar_violacoes(texto) == []


def test_encontrar_violacoes_retorna_o_trecho_normalizado_sem_repeticao():
    assert encontrar_violacoes("Compre PETR4. Compre VALE3.") == ["compre"]


def test_montar_reforco_lista_os_termos_encontrados():
    reforco = montar_reforco(["compre", "recomendo"])

    assert '"compre"' in reforco
    assert '"recomendo"' in reforco
    assert "imperativos" in reforco
