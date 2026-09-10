from uuid import uuid4

from app.domain.regras_sinal_padrao import REGRAS_PADRAO, buscar_regra_por_id


def test_regras_padrao_tem_ids_unicos():
    ids = [regra.id for regra in REGRAS_PADRAO]
    assert len(ids) == len(set(ids))


def test_regras_padrao_todas_ativas_por_padrao():
    assert all(regra.ativa for regra in REGRAS_PADRAO)


def test_buscar_regra_por_id_encontra_regra_existente():
    primeira = REGRAS_PADRAO[0]

    encontrada = buscar_regra_por_id(primeira.id)

    assert encontrada is primeira


def test_buscar_regra_por_id_inexistente_retorna_none():
    assert buscar_regra_por_id(uuid4()) is None


def test_sobrevenda_rsi_condicoes():
    regra = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")

    assert regra.condicoes == {
        "tipo_indicador": "RSI",
        "parametros": {"periodo": 14},
        "operador": "menor_que",
        "valor_limiar": 30,
    }


def test_pico_de_volume_condicoes():
    regra = next(r for r in REGRAS_PADRAO if r.nome == "Pico de Volume")

    assert regra.condicoes == {
        "tipo_indicador": "VOLUME_RELATIVO",
        "parametros": {"periodo": 20},
        "operador": "maior_que",
        "valor_limiar": 1.5,
    }
