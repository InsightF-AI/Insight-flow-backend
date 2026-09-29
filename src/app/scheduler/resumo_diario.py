from __future__ import annotations

import logging
import time
from collections.abc import Callable

from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.services.exceptions import LLMCotaExcedidaError
from app.services.resumo_carteira_service import ResumoCarteiraService

logger = logging.getLogger(__name__)


def gerar_resumos_diarios(
    operacao_repository: OperacaoRepository,
    resumo_service: ResumoCarteiraService,
    pausa_segundos: float,
    dormir: Callable[[float], None] = time.sleep,
    ao_falhar_usuario: Callable[[], None] | None = None,
) -> None:
    for usuario_id in operacao_repository.listar_usuarios_com_operacoes():
        try:
            notificacao = resumo_service.gerar(usuario_id)
        except LLMCotaExcedidaError:
            logger.warning("Cota do provedor de IA excedida; resumo diario interrompido.")
            return
        except Exception:
            logger.warning(
                "Falha ao gerar o resumo diario do usuario %s.", usuario_id, exc_info=True
            )
            if ao_falhar_usuario is not None:
                ao_falhar_usuario()
            continue

        if notificacao is not None:
            dormir(pausa_segundos)
