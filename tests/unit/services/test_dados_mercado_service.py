from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado
from app.services.dados_mercado_service import DadosMercadoService


class _BrapiClientFalso:
    def __init__(self, resultado: list[AtivoEncontrado]):
        self._resultado = resultado
        self.termo_recebido = None

    def buscar_ativos(self, termo: str) -> list[AtivoEncontrado]:
        self.termo_recebido = termo
        return self._resultado


def test_buscar_ativo_delega_para_o_cliente_brapi():
    encontrado = AtivoEncontrado(
        ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo"
    )
    brapi_client = _BrapiClientFalso([encontrado])
    service = DadosMercadoService(brapi_client)

    resultado = service.buscar_ativo("petr4")

    assert resultado == [encontrado]
    assert brapi_client.termo_recebido == "petr4"
