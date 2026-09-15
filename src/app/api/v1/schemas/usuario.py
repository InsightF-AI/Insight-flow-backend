from pydantic import BaseModel, EmailStr, Field


class CadastroRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)
