from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.logs import correlation_id_atual


def criar_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url)
    fabrica = sessionmaker(bind=engine)
    event.listen(fabrica, "after_begin", marcar_correlacao_na_transacao)
    return fabrica


def marcar_correlacao_na_transacao(session: Session, transaction, connection) -> None:
    correlation_id = correlation_id_atual()
    if correlation_id:
        connection.execute(
            text("SELECT set_config('app.correlation_id', :valor, true)"),
            {"valor": correlation_id},
        )
