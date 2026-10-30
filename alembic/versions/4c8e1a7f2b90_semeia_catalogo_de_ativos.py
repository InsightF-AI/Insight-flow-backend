"""semeia o catalogo inicial de ativos

Revision ID: 4c8e1a7f2b90
Revises: b7d9f1a3c5e7
Create Date: 2026-10-30 13:00:00.000000

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "4c8e1a7f2b90"
down_revision: str | Sequence[str] | None = "b7d9f1a3c5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATALOGO = [
    ("PETR4", "PETROLEO BRASILEIRO S.A. PETROBRAS", "ACAO", "Energy Minerals", "BRL", "brapi"),
    ("VALE3", "VALE S.A.", "ACAO", "Non-Energy Minerals", "BRL", "brapi"),
    ("ITUB4", "ITAU UNIBANCO HOLDING S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("BBDC4", "BCO BRADESCO S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("BBAS3", "BCO BRASIL S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("ABEV3", "AMBEV S.A.", "ACAO", "Consumer Non-Durables", "BRL", "brapi"),
    ("WEGE3", "WEG S.A.", "ACAO", "Producer Manufacturing", "BRL", "brapi"),
    ("B3SA3", "B3 S.A. - BRASIL. BOLSA. BALCÃO", "ACAO", "Finance", "BRL", "brapi"),
    ("ITSA4", "ITAUSA S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("RENT3", "LOCALIZA RENT A CAR S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("SUZB3", "SUZANO S.A.", "ACAO", "Process Industries", "BRL", "brapi"),
    ("AXIA3", "AXIA ENERGIA S.A.", "ACAO", "Utilities", "BRL", "brapi"),
    ("PRIO3", "PRIO S.A.", "ACAO", "Energy Minerals", "BRL", "brapi"),
    ("RADL3", "RAIA DROGASIL S.A.", "ACAO", "Retail Trade", "BRL", "brapi"),
    ("EQTL3", "EQUATORIAL S.A.", "ACAO", "Utilities", "BRL", "brapi"),
    ("GGBR4", "GERDAU S.A.", "ACAO", "Non-Energy Minerals", "BRL", "brapi"),
    ("MGLU3", "MAGAZINE LUIZA S.A.", "ACAO", "Retail Trade", "BRL", "brapi"),
    ("LREN3", "LOJAS RENNER S.A.", "ACAO", "Retail Trade", "BRL", "brapi"),
    ("VIVT3", "TELEFÔNICA BRASIL S.A", "ACAO", "Communications", "BRL", "brapi"),
    ("BPAC11", "BCO BTG PACTUAL S.A.", "ACAO", "Finance", "BRL", "brapi"),
    ("RAIL3", "RUMO S.A.", "ACAO", "Transportation", "BRL", "brapi"),
    ("CMIG4", "CIA ENERGETICA DE MINAS GERAIS - CEMIG", "ACAO", "Utilities", "BRL", "brapi"),
    ("SBSP3", "CIA SANEAMENTO BASICO EST SAO PAULO", "ACAO", "Utilities", "BRL", "brapi"),
    (
        "MXRF11",
        "MAXI RENDA FUNDO DE INVESTIMENTO IMOBILIÁRIO - FII - RESPONSABILIDADE LIMITADA",
        "FII",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    (
        "HGLG11",
        "PÁTRIA LOG - FUNDO DE INVESTIMENTO IMOBILIÁRIO - RESPONSABILIDADE LIMITADA",
        "FII",
        "Finance",
        "BRL",
        "brapi",
    ),
    (
        "KNRI11",
        "KINEA RENDA IMOBILIÁRIA FUNDO DE INVESTIMENTO IMOBILIÁRIO RESPONSABILIDADE LIMITADA",
        "FII",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    ("XPML11", "XP MALLS FUNDO DE INVESTIMENTO IMOBILIÁRIO FII", "FII", "Finance", "BRL", "brapi"),
    (
        "VISC11",
        "VINCI SHOPPING CENTERS FUNDO DE INVESTIMENTO IMOBILIÁRIO - RESPONSABILIDADE LIMITADA",
        "FII",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    (
        "BOVA11",
        "ISHARES IBOVESPA CLASSE DE ÍNDICE - RESPONSABILIDADE LIMITADA",
        "ETF",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    (
        "IVVB11",
        "ISHARES S&P 500 CLASSE DE ÍNDICE EM COTAS DE CLASSES DE ÍNDICE IE - RESPONSABILIDADE LIMITADA",
        "ETF",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    (
        "SMAL11",
        "ISHARES BM&FBOVESPA SMALL CAP CLASSE DE  ÍNDICE - RESPONSABILIDADE LIMITADA",
        "ETF",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    (
        "HASH11",
        "HASHDEX NASDAQ CME CRYPTO INDEX FUNDO DE ÍNDICE - RESPONSABILIDADE LIMITADA",
        "ETF",
        "Miscellaneous",
        "BRL",
        "brapi",
    ),
    ("BTC", "Bitcoin", "CRIPTO", None, "BRL", "binance"),
    ("ETH", "Ethereum", "CRIPTO", None, "BRL", "binance"),
    ("SOL", "Solana", "CRIPTO", None, "BRL", "binance"),
    ("XRP", "XRP", "CRIPTO", None, "BRL", "binance"),
    ("BNB", "BNB", "CRIPTO", None, "BRL", "binance"),
    ("ADA", "Cardano", "CRIPTO", None, "BRL", "binance"),
    ("DOGE", "Dogecoin", "CRIPTO", None, "BRL", "binance"),
    ("USDT", "Tether", "CRIPTO", None, "BRL", "binance"),
    ("LINK", "Chainlink", "CRIPTO", None, "BRL", "binance"),
    ("AVAX", "Avalanche", "CRIPTO", None, "BRL", "binance"),
    ("LTC", "Litecoin", "CRIPTO", None, "BRL", "binance"),
]

_ativos = sa.table(
    "ativos",
    sa.column("id", sa.Uuid()),
    sa.column("ticker", sa.String()),
    sa.column("nome", sa.String()),
    sa.column("tipo", sa.String()),
    sa.column("setor", sa.String()),
    sa.column("moeda", sa.String()),
    sa.column("fonte_dados", sa.String()),
)


def upgrade() -> None:
    op.get_bind().execute(
        insert(_ativos)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "ticker": ticker,
                    "nome": nome,
                    "tipo": tipo,
                    "setor": setor,
                    "moeda": moeda,
                    "fonte_dados": fonte_dados,
                }
                for ticker, nome, tipo, setor, moeda, fonte_dados in _CATALOGO
            ]
        )
        .on_conflict_do_nothing(index_elements=["ticker"])
    )


def downgrade() -> None:
    pass
