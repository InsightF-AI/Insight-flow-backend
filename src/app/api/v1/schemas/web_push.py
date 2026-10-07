from pydantic import BaseModel


class ChavesInscricaoRequest(BaseModel):
    p256dh: str
    auth: str


class RegistrarInscricaoRequest(BaseModel):
    endpoint: str
    keys: ChavesInscricaoRequest


class InscricaoResponse(BaseModel):
    endpoint: str


class ChavePublicaResponse(BaseModel):
    chave_publica: str
