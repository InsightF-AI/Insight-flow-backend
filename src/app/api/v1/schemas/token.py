from pydantic import BaseModel

from app.services.refresh_token_service import ParTokens


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

    @staticmethod
    def de(par: ParTokens) -> "TokenResponse":
        return TokenResponse(
            access_token=par.access_token,
            refresh_token=par.refresh_token,
            expires_in=par.expires_in,
        )
