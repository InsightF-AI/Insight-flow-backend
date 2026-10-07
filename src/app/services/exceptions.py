class EmailJaCadastradoError(Exception):
    pass


class CredenciaisInvalidasError(Exception):
    pass


class AtivoJaNaWatchlistError(Exception):
    pass


class ItemWatchlistNaoEncontradoError(Exception):
    pass


class AtivoNaoEncontradoError(Exception):
    pass


class RegraNaoEncontradaError(Exception):
    pass


class MoedaNaoSuportadaError(Exception):
    pass


class AlertaNaoEncontradoError(Exception):
    pass


class NotificacaoNaoEncontradaError(Exception):
    pass


class QuantidadeInsuficienteError(Exception):
    pass


class OperacaoInvalidaError(Exception):
    pass


class OperacaoNaoEncontradaError(Exception):
    pass


class PortfolioVazioError(Exception):
    pass


class LLMIndisponivelError(Exception):
    pass


class LLMCotaExcedidaError(Exception):
    def __init__(self, retry_after: int | None = None):
        super().__init__("Cota do provedor de IA excedida")
        self.retry_after = retry_after


class RespostaViolaGuardrailError(Exception):
    pass


class ContextoInsuficienteError(Exception):
    pass


class RefreshTokenInvalidoError(Exception):
    pass


class TokenPushInvalidoError(Exception):
    pass
