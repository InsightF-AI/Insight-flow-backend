from pydantic import BaseModel


class RegistrarDispositivoRequest(BaseModel):
    token: str


class DispositivoResponse(BaseModel):
    token: str
    ativo: bool
