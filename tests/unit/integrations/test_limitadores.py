from app.integrations.limitadores import limitador_compartilhado


def test_mesmo_provedor_e_configuracao_reutiliza_o_limitador():
    primeiro = limitador_compartilhado("brapi", 60, 10.0)
    segundo = limitador_compartilhado("brapi", 60, 10.0)

    assert primeiro is segundo


def test_provedores_diferentes_tem_limitadores_independentes():
    assert limitador_compartilhado("brapi", 60, 10.0) is not limitador_compartilhado(
        "binance", 60, 10.0
    )
