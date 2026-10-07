from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.correlacao import CorrelacaoMiddleware
from app.api.v1.controllers.alertas import router as alertas_router
from app.api.v1.controllers.analise_ia import router as analise_ia_router
from app.api.v1.controllers.ativos import router as ativos_router
from app.api.v1.controllers.auth import router as auth_router
from app.api.v1.controllers.notificacoes import router as notificacoes_router
from app.api.v1.controllers.portfolio import router as portfolio_router
from app.api.v1.controllers.usuarios import router as usuarios_router
from app.api.v1.controllers.watchlist import router as watchlist_router
from app.core.config import get_settings
from app.core.logs import configurar_logs
from app.scheduler.jobs import registrar_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler = BackgroundScheduler()
    if settings.scheduler_habilitado:
        registrar_jobs(scheduler, settings)
        scheduler.start()
    yield
    if settings.scheduler_habilitado:
        scheduler.shutdown(wait=False)


configurar_logs(get_settings().log_nivel, get_settings().log_formato)

app = FastAPI(title="InsightFlow AI - Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origens,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(CorrelacaoMiddleware)
app.include_router(usuarios_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(watchlist_router, prefix="/api/v1")
app.include_router(ativos_router, prefix="/api/v1")
app.include_router(alertas_router, prefix="/api/v1")
app.include_router(notificacoes_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(analise_ia_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
