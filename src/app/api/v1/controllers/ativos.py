from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_dados_mercado_service, get_usuario_atual
from app.api.v1.schemas.ativo import AtivoEncontradoResponse
from app.domain.entities.usuario import Usuario
from app.integrations.brapi.client import BrapiIndisponivelError
from app.services.dados_mercado_service import DadosMercadoService

router = APIRouter(prefix="/ativos", tags=["ativos"])


@router.get("/buscar", response_model=list[AtivoEncontradoResponse])
def buscar(
    termo: str,
    usuario: Usuario = Depends(get_usuario_atual),
    service: DadosMercadoService = Depends(get_dados_mercado_service),
) -> list[AtivoEncontradoResponse]:
    try:
        encontrados = service.buscar_ativo(termo)
    except BrapiIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de mercado indisponivel"
        ) from exc

    return [AtivoEncontradoResponse.de(ativo) for ativo in encontrados]
