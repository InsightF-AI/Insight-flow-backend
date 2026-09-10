from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_ativo_service,
    get_dados_mercado_service,
    get_indicador_service,
    get_usuario_atual,
)
from app.api.v1.schemas.ativo import AtivoEncontradoResponse
from app.api.v1.schemas.cotacao import CotacaoAtualResponse, PontoHistoricoResponse
from app.api.v1.schemas.indicador import IndicadorTecnicoResponse
from app.domain.entities.usuario import Usuario
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError
from app.services.ativo_service import AtivoService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.indicador_service import IndicadorService

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


@router.get("/{ativo_id}/cotacao", response_model=CotacaoAtualResponse)
def cotacao_atual(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AtivoService = Depends(get_ativo_service),
) -> CotacaoAtualResponse:
    try:
        cotacao = service.cotacao_atual(ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except TickerNaoEncontradoError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Cotacao nao encontrada para o ativo"
        ) from exc
    except BrapiIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de mercado indisponivel"
        ) from exc

    return CotacaoAtualResponse.de(cotacao)


@router.get("/{ativo_id}/historico", response_model=list[PontoHistoricoResponse])
def historico(
    ativo_id: UUID,
    periodo: PeriodoHistorico = PeriodoHistorico.UM_MES,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AtivoService = Depends(get_ativo_service),
) -> list[PontoHistoricoResponse]:
    try:
        pontos = service.historico(ativo_id, periodo)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except TickerNaoEncontradoError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Historico nao encontrado para o ativo"
        ) from exc
    except BrapiIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de mercado indisponivel"
        ) from exc

    return [PontoHistoricoResponse.de(ponto) for ponto in pontos]


@router.get("/{ativo_id}/indicadores", response_model=list[IndicadorTecnicoResponse])
def indicadores(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: IndicadorService = Depends(get_indicador_service),
) -> list[IndicadorTecnicoResponse]:
    try:
        calculados = service.calcular_todos(ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc

    return [IndicadorTecnicoResponse.de(indicador) for indicador in calculados]
