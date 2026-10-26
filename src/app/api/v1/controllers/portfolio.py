from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_portfolio_service, get_provento_service, get_usuario_atual
from app.api.v1.schemas.portfolio import (
    ComparativoResponse,
    DistribuicaoResponse,
    OperacaoResponse,
    PosicaoResponse,
    RegistrarOperacaoRequest,
    RentabilidadeResponse,
)
from app.api.v1.schemas.provento import ResumoProventosResponse
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.integrations.erros import FonteDadosIndisponivelError
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
    PortfolioVazioError,
    QuantidadeInsuficienteError,
)
from app.services.portfolio_service import PortfolioService
from app.services.provento_service import ProventoService

router = APIRouter(tags=["portfolio"])


@router.post("/operacoes", status_code=status.HTTP_201_CREATED, response_model=OperacaoResponse)
def registrar_operacao(
    dados: RegistrarOperacaoRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> OperacaoResponse:
    try:
        operacao = service.registrar_operacao(
            usuario_id=usuario.id,
            ativo_id=dados.ativo_id,
            tipo=dados.tipo,
            quantidade=dados.quantidade,
            preco_unitario=dados.preco_unitario,
            data=dados.data,
        )
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except (OperacaoInvalidaError, QuantidadeInsuficienteError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return OperacaoResponse.de(operacao)


@router.get("/operacoes", response_model=list[OperacaoResponse])
def listar_operacoes(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[OperacaoResponse]:
    return [OperacaoResponse.de(op) for op in service.listar_operacoes(usuario.id)]


@router.delete("/operacoes/{operacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_operacao(
    operacao_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> None:
    try:
        service.remover_operacao(usuario.id, operacao_id)
    except OperacaoNaoEncontradaError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operacao nao encontrada") from exc
    except QuantidadeInsuficienteError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/portfolio/posicoes", response_model=list[PosicaoResponse])
def posicoes(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[PosicaoResponse]:
    return [PosicaoResponse.de(p) for p in service.posicoes(usuario.id)]


@router.get("/portfolio/rentabilidade", response_model=RentabilidadeResponse)
def rentabilidade(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> RentabilidadeResponse:
    return RentabilidadeResponse.de(service.rentabilidade(usuario.id))


@router.get("/portfolio/benchmark", response_model=ComparativoResponse)
def comparativo_benchmark(
    benchmark: TipoBenchmark,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ComparativoResponse:
    try:
        comparativo = service.comparativo_benchmark(usuario.id, benchmark)
    except PortfolioVazioError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma operacao registrada") from exc

    return ComparativoResponse.de(comparativo)


@router.get("/portfolio/distribuicao", response_model=DistribuicaoResponse)
def distribuicao(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> DistribuicaoResponse:
    return DistribuicaoResponse.de(service.distribuicao(usuario.id))


@router.get("/portfolio/dividendos", response_model=ResumoProventosResponse)
def dividendos_recebidos(
    usuario: Usuario = Depends(get_usuario_atual),
    service: ProventoService = Depends(get_provento_service),
) -> ResumoProventosResponse:
    try:
        resumo = service.recebidos(usuario.id)
    except FonteDadosIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de proventos indisponivel"
        ) from exc

    return ResumoProventosResponse.de(resumo)
