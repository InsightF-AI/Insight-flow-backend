from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from app.ai.contexto import calcular_hash, serializar
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.distribuicao import Distribuicao


@dataclass
class _Exemplo:
    id: UUID
    valor: Decimal
    tipo: TipoAtivo
    quando: datetime
    dia: date


def test_serializar_converte_tipos_nao_json():
    exemplo = _Exemplo(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        valor=Decimal("10.50"),
        tipo=TipoAtivo.ACAO,
        quando=datetime(2026, 9, 29, 12, 0, tzinfo=UTC),
        dia=date(2026, 9, 29),
    )

    assert serializar(exemplo) == {
        "id": "11111111-1111-1111-1111-111111111111",
        "valor": "10.50",
        "tipo": "ACAO",
        "quando": "2026-09-29T12:00:00+00:00",
        "dia": "2026-09-29",
    }


def test_serializar_converte_chaves_enum_de_dict():
    distribuicao = Distribuicao(
        por_classe={TipoAtivo.ACAO: Decimal("0.6")},
        por_setor={"Energia": Decimal("0.4")},
        por_moeda={"BRL": Decimal(1)},
    )

    resultado = serializar(distribuicao)

    assert resultado["por_classe"] == {"ACAO": "0.6"}
    assert resultado["por_setor"] == {"Energia": "0.4"}


def test_serializar_lista_e_none():
    assert serializar([Decimal(1), None, "x"]) == ["1", None, "x"]


def test_hash_tem_64_caracteres_hex():
    assert len(calcular_hash({"a": 1})) == 64


def test_hash_ignora_ordem_das_chaves():
    assert calcular_hash({"a": 1, "b": 2}) == calcular_hash({"b": 2, "a": 1})


def test_hash_muda_quando_um_valor_muda():
    assert calcular_hash({"a": Decimal(1)}) != calcular_hash({"a": Decimal(2)})


def test_hash_e_estavel_para_o_mesmo_contexto_com_decimal_e_enum():
    contexto = {"tipo": TipoAtivo.FII, "valor": Decimal("3.1400")}

    assert calcular_hash(contexto) == calcular_hash(dict(contexto))
