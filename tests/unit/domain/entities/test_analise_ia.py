from datetime import datetime
from uuid import uuid4

from app.domain.entities.analise_ia import AnaliseIA


def test_cria_analise_ia_com_dados_de_rastreabilidade_do_provedor():
    analise = AnaliseIA(
        id=uuid4(),
        ativo_id=uuid4(),
        texto="O RSI encontra-se em região de sobrevenda.",
        provedor="claude",
        modelo="claude-sonnet-5",
        prompt_versao="v1",
        contexto_hash="abc123",
        gerado_em=datetime(2026, 9, 8, 18, 0, 0),
    )

    assert analise.provedor == "claude"
    assert analise.contexto_hash == "abc123"
