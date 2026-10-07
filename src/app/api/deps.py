from collections.abc import Callable, Generator
from functools import lru_cache
from uuid import UUID

import httpx
import redis
import redis.asyncio
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.ai.ferramentas_chat import ExecutorFerramentas
from app.ai.providers.base import ProvedorLLM
from app.ai.providers.fabrica import criar_provedor_llm
from app.api.correlacao import registrar_usuario_na_requisicao
from app.core.config import Settings, get_settings
from app.core.security import TokenInvalidoError, decodificar_token
from app.db.session import criar_session_factory
from app.domain.entities.usuario import Usuario
from app.integrations.bcb.client import BcbClient
from app.integrations.binance.client import BinanceClient
from app.integrations.brapi.client import BrapiClient
from app.integrations.expo.fabrica import criar_expo_client
from app.integrations.limitadores import limitador_compartilhado
from app.integrations.web_push.fabrica import criar_web_push_client
from app.notifications.barramento import BarramentoNotificacoes
from app.notifications.canais import montar_canais
from app.notifications.redis_barramento import RedisBarramentoNotificacoes
from app.repositories.interfaces.alerta_repository import AlertaRepository
from app.repositories.interfaces.analise_ia_repository import AnaliseIARepository
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.repositories.interfaces.watchlist_repository import WatchlistRepository
from app.repositories.sqlalchemy.alerta_repository import SqlAlchemyAlertaRepository
from app.repositories.sqlalchemy.analise_ia_repository import SqlAlchemyAnaliseIARepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.cotacao_repository import SqlAlchemyCotacaoRepository
from app.repositories.sqlalchemy.dispositivo_push_repository import (
    SqlAlchemyDispositivoPushRepository,
)
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)
from app.repositories.sqlalchemy.inscricao_web_push_repository import (
    SqlAlchemyInscricaoWebPushRepository,
)
from app.repositories.sqlalchemy.notificacao_repository import SqlAlchemyNotificacaoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.repositories.sqlalchemy.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository
from app.repositories.sqlalchemy.ticket_push_repository import SqlAlchemyTicketPushRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository
from app.services.alerta_service import AlertaService
from app.services.analise_ia_service import AnaliseIAService
from app.services.ativo_service import AtivoService
from app.services.cached_cambio_service import CachedCambioService
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.cambio_service import BcbCambioService, CambioService
from app.services.chat_service import ChatService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.dispositivo_push_service import DispositivoPushService
from app.services.exceptions import LLMIndisponivelError
from app.services.indicador_service import IndicadorService
from app.services.inscricao_web_push_service import InscricaoWebPushService
from app.services.mercado_cache import MercadoCache
from app.services.notificacao_service import NotificacaoService
from app.services.portfolio_service import PortfolioService
from app.services.redis_mercado_cache import RedisMercadoCache
from app.services.refresh_token_service import RefreshTokenService
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from app.services.sinal_service import SinalService
from app.services.usuario_service import UsuarioService
from app.services.watchlist_service import WatchlistService

_bearer_scheme = HTTPBearer()


@lru_cache
def _session_factory(database_url: str) -> sessionmaker:
    return criar_session_factory(database_url)


def get_db_session(settings: Settings = Depends(get_settings)) -> Generator[Session, None, None]:
    session = _session_factory(settings.database_url)()
    try:
        yield session
    finally:
        session.close()


def get_usuario_repository(
    session: Session = Depends(get_db_session),
) -> UsuarioRepository:
    return SqlAlchemyUsuarioRepository(session)


def get_refresh_token_repository(
    session: Session = Depends(get_db_session),
) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_dispositivo_push_repository(
    session: Session = Depends(get_db_session),
) -> DispositivoPushRepository:
    return SqlAlchemyDispositivoPushRepository(session)


def get_ticket_push_repository(
    session: Session = Depends(get_db_session),
) -> TicketPushRepository:
    return SqlAlchemyTicketPushRepository(session)


def get_dispositivo_push_service(
    dispositivo_repository: DispositivoPushRepository = Depends(get_dispositivo_push_repository),
) -> DispositivoPushService:
    return DispositivoPushService(dispositivo_repository)


def get_inscricao_web_push_repository(
    session: Session = Depends(get_db_session),
) -> InscricaoWebPushRepository:
    return SqlAlchemyInscricaoWebPushRepository(session)


def get_inscricao_web_push_service(
    inscricao_repository: InscricaoWebPushRepository = Depends(get_inscricao_web_push_repository),
    settings: Settings = Depends(get_settings),
) -> InscricaoWebPushService:
    return InscricaoWebPushService(inscricao_repository, settings.web_push_hosts_permitidos)


def get_refresh_token_service(
    refresh_token_repository: RefreshTokenRepository = Depends(get_refresh_token_repository),
    usuario_repository: UsuarioRepository = Depends(get_usuario_repository),
    settings: Settings = Depends(get_settings),
) -> RefreshTokenService:
    return RefreshTokenService(
        refresh_token_repository,
        usuario_repository,
        jwt_secret_key=settings.jwt_secret_key,
        access_expiracao_minutos=settings.jwt_expiration_minutes,
        refresh_expiracao_dias=settings.refresh_token_expiracao_dias,
    )


def get_usuario_service(
    repository: UsuarioRepository = Depends(get_usuario_repository),
) -> UsuarioService:
    return UsuarioService(repository)


def get_ativo_repository(
    session: Session = Depends(get_db_session),
) -> AtivoRepository:
    return SqlAlchemyAtivoRepository(session)


def get_watchlist_repository(
    session: Session = Depends(get_db_session),
) -> WatchlistRepository:
    return SqlAlchemyWatchlistRepository(session)


def get_cotacao_repository(
    session: Session = Depends(get_db_session),
) -> CotacaoRepository:
    return SqlAlchemyCotacaoRepository(session)


def get_indicador_tecnico_repository(
    session: Session = Depends(get_db_session),
) -> IndicadorTecnicoRepository:
    return SqlAlchemyIndicadorTecnicoRepository(session)


def get_sinal_repository(
    session: Session = Depends(get_db_session),
) -> SinalRepository:
    return SqlAlchemySinalRepository(session)


def get_alerta_repository(
    session: Session = Depends(get_db_session),
) -> AlertaRepository:
    return SqlAlchemyAlertaRepository(session)


def get_notificacao_repository(
    session: Session = Depends(get_db_session),
) -> NotificacaoRepository:
    return SqlAlchemyNotificacaoRepository(session)


@lru_cache
def _brapi_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_brapi_client(settings: Settings = Depends(get_settings)) -> BrapiClient:
    return BrapiClient(
        _brapi_http_client(settings.brapi_base_url),
        settings.brapi_api_key or None,
        limitador=limitador_compartilhado(
            "brapi",
            settings.brapi_requisicoes_por_minuto,
            settings.integracoes_espera_maxima_segundos,
        ),
        politica=settings.politica_retentativa(),
    )


@lru_cache
def _bcb_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_bcb_client(settings: Settings = Depends(get_settings)) -> BcbClient:
    return BcbClient(_bcb_http_client(settings.bcb_base_url))


@lru_cache
def _redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


def get_mercado_cache(settings: Settings = Depends(get_settings)) -> MercadoCache:
    return RedisMercadoCache(_redis_client(settings.redis_url))


@lru_cache
def _redis_async_client(redis_url: str) -> redis.asyncio.Redis:
    return redis.asyncio.Redis.from_url(redis_url)


def get_barramento_notificacoes(
    settings: Settings = Depends(get_settings),
) -> BarramentoNotificacoes:
    return RedisBarramentoNotificacoes(
        _redis_client(settings.redis_url), _redis_async_client(settings.redis_url)
    )


def get_buscador_usuario(
    settings: Settings = Depends(get_settings),
) -> Callable[[UUID], Usuario | None]:
    fabrica = _session_factory(settings.database_url)

    def buscar(usuario_id: UUID) -> Usuario | None:
        with fabrica() as session:
            return SqlAlchemyUsuarioRepository(session).buscar_por_id(usuario_id)

    return buscar


@lru_cache
def _binance_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_binance_client(settings: Settings = Depends(get_settings)) -> BinanceClient:
    return BinanceClient(
        _binance_http_client(settings.binance_base_url),
        limitador=limitador_compartilhado(
            "binance",
            settings.binance_requisicoes_por_minuto,
            settings.integracoes_espera_maxima_segundos,
        ),
        politica=settings.politica_retentativa(),
    )


def get_dados_mercado_service(
    brapi_client: BrapiClient = Depends(get_brapi_client),
    binance_client: BinanceClient = Depends(get_binance_client),
    mercado_cache: MercadoCache = Depends(get_mercado_cache),
    settings: Settings = Depends(get_settings),
) -> DadosMercadoService:
    return CachedDadosMercadoService(
        RoteadorDadosMercadoService(
            DadosMercadoService(brapi_client),
            binance_client,
            mercado_cache,
            ttl_catalogo_segundos=settings.cache_ttl_catalogo_cripto_segundos,
        ),
        mercado_cache,
        ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
        ttl_historico=settings.cache_ttl_historico_segundos,
    )


def get_cambio_service(
    bcb_client: BcbClient = Depends(get_bcb_client),
    mercado_cache: MercadoCache = Depends(get_mercado_cache),
    settings: Settings = Depends(get_settings),
) -> CambioService:
    return CachedCambioService(
        BcbCambioService(bcb_client),
        mercado_cache,
        ttl_segundos=settings.cache_ttl_cambio_segundos,
        ttl_fallback_segundos=settings.cache_ttl_cambio_fallback_segundos,
    )


def get_ativo_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
) -> AtivoService:
    return AtivoService(ativo_repository, dados_mercado_service, cotacao_repository)


def get_indicador_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_repository: IndicadorTecnicoRepository = Depends(get_indicador_tecnico_repository),
) -> IndicadorService:
    return IndicadorService(ativo_repository, cotacao_repository, indicador_repository)


def get_sinal_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_service: IndicadorService = Depends(get_indicador_service),
    sinal_repository: SinalRepository = Depends(get_sinal_repository),
) -> SinalService:
    return SinalService(ativo_repository, cotacao_repository, indicador_service, sinal_repository)


def get_watchlist_service(
    watchlist_repository: WatchlistRepository = Depends(get_watchlist_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    ativo_service: AtivoService = Depends(get_ativo_service),
    settings: Settings = Depends(get_settings),
) -> WatchlistService:
    return WatchlistService(
        watchlist_repository,
        ativo_repository,
        dados_mercado_service,
        ativo_service,
        politica=settings.politica_historico(),
    )


def get_alerta_service(
    alerta_repository: AlertaRepository = Depends(get_alerta_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cambio_service: CambioService = Depends(get_cambio_service),
) -> AlertaService:
    return AlertaService(alerta_repository, ativo_repository, dados_mercado_service, cambio_service)


def get_operacao_repository(
    session: Session = Depends(get_db_session),
) -> OperacaoRepository:
    return SqlAlchemyOperacaoRepository(session)


def get_portfolio_service(
    operacao_repository: OperacaoRepository = Depends(get_operacao_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cambio_service: CambioService = Depends(get_cambio_service),
    bcb_client: BcbClient = Depends(get_bcb_client),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
) -> PortfolioService:
    return PortfolioService(
        operacao_repository,
        ativo_repository,
        dados_mercado_service,
        cambio_service,
        bcb_client,
        cotacao_repository,
    )


def get_notificacao_service(
    notificacao_repository: NotificacaoRepository = Depends(get_notificacao_repository),
    barramento: BarramentoNotificacoes = Depends(get_barramento_notificacoes),
    dispositivo_repository: DispositivoPushRepository = Depends(get_dispositivo_push_repository),
    ticket_repository: TicketPushRepository = Depends(get_ticket_push_repository),
    inscricao_repository: InscricaoWebPushRepository = Depends(get_inscricao_web_push_repository),
    settings: Settings = Depends(get_settings),
) -> NotificacaoService:
    return NotificacaoService(
        notificacao_repository,
        canais=montar_canais(
            settings,
            barramento,
            dispositivo_repository,
            ticket_repository,
            criar_expo_client(settings),
            inscricao_repository,
            criar_web_push_client(settings),
        ),
    )


def get_analise_ia_repository(
    session: Session = Depends(get_db_session),
) -> AnaliseIARepository:
    return SqlAlchemyAnaliseIARepository(session)


def get_provedor_llm(settings: Settings = Depends(get_settings)) -> ProvedorLLM:
    try:
        return criar_provedor_llm(settings)
    except LLMIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Provedor de IA indisponivel"
        ) from exc


def get_analise_ia_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_service: IndicadorService = Depends(get_indicador_service),
    sinal_service: SinalService = Depends(get_sinal_service),
    analise_repository: AnaliseIARepository = Depends(get_analise_ia_repository),
    provedor: ProvedorLLM = Depends(get_provedor_llm),
) -> AnaliseIAService:
    return AnaliseIAService(
        ativo_repository,
        cotacao_repository,
        indicador_service,
        sinal_service,
        analise_repository,
        provedor,
    )


def get_chat_service(
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    provedor: ProvedorLLM = Depends(get_provedor_llm),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    return ChatService(
        provedor,
        ExecutorFerramentas(portfolio_service, ativo_repository),
        settings.max_iteracoes_ferramentas,
    )


def get_usuario_atual(
    request: Request,
    credenciais: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    service: UsuarioService = Depends(get_usuario_service),
    settings: Settings = Depends(get_settings),
) -> Usuario:
    try:
        usuario_id = decodificar_token(credenciais.credentials, settings.jwt_secret_key)
    except TokenInvalidoError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido") from exc

    usuario = service.buscar_por_id(usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario nao encontrado")
    registrar_usuario_na_requisicao(request, usuario.id)
    return usuario
