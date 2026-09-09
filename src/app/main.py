from fastapi import FastAPI

from app.api.v1.controllers.ativos import router as ativos_router
from app.api.v1.controllers.auth import router as auth_router
from app.api.v1.controllers.usuarios import router as usuarios_router
from app.api.v1.controllers.watchlist import router as watchlist_router

app = FastAPI(title="InsightFlow AI - Backend")
app.include_router(usuarios_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(watchlist_router, prefix="/api/v1")
app.include_router(ativos_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
