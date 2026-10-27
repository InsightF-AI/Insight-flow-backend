from app.core.logs import em_correlacao
from app.db.session import marcar_correlacao_na_transacao


class _ConexaoFalsa:
    def __init__(self):
        self.executados: list[tuple[str, dict]] = []

    def execute(self, comando, parametros):
        self.executados.append((str(comando), parametros))


def test_marca_o_correlation_id_na_transacao():
    conexao = _ConexaoFalsa()

    with em_correlacao("req-123"):
        marcar_correlacao_na_transacao(None, None, conexao)

    [(sql, parametros)] = conexao.executados
    assert "set_config('app.correlation_id'" in sql
    assert parametros == {"valor": "req-123"}


def test_sem_correlation_id_nao_executa_nada():
    conexao = _ConexaoFalsa()

    marcar_correlacao_na_transacao(None, None, conexao)

    assert conexao.executados == []
