from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo


def test_cria_ativo_com_todos_os_atributos_da_especificacao():
    ativo_id = uuid4()

    ativo = Ativo(
        id=ativo_id,
        ticker="PETR4",
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petróleo e Gás",
        moeda="BRL",
        fonte_dados="brapi",
    )

    assert ativo.id == ativo_id
    assert ativo.ticker == "PETR4"
    assert ativo.tipo is TipoAtivo.ACAO
    assert ativo.moeda == "BRL"
