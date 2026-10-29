"""cria tabela auditoria e triggers nas tabelas de dados do usuario

Revision ID: c2e8a4f6b913
Revises: b7d9f1a3c5e7
Create Date: 2026-10-27 01:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2e8a4f6b913"
down_revision: str | Sequence[str] | None = "b7d9f1a3c5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS_AUDITADAS = (
    "usuarios",
    "refresh_tokens",
    "operacoes",
    "watchlists",
    "alertas_personalizados",
    "dispositivos_push",
    "inscricoes_web_push",
)

CRIAR_TABELA = """
CREATE TABLE auditoria (
    id BIGSERIAL PRIMARY KEY,
    ocorrido_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    tabela TEXT NOT NULL,
    operacao TEXT NOT NULL,
    registro_id TEXT,
    usuario_id UUID,
    correlation_id TEXT,
    usuario_banco TEXT NOT NULL DEFAULT current_user,
    dados_antes JSONB,
    dados_depois JSONB
);
CREATE INDEX ix_auditoria_tabela_registro ON auditoria (tabela, registro_id);
CREATE INDEX ix_auditoria_usuario_ocorrido ON auditoria (usuario_id, ocorrido_em);
CREATE INDEX ix_auditoria_correlation_id ON auditoria (correlation_id);
"""

# Segredos e credenciais de push nunca entram na trilha. Um UPDATE que só mexe nessas
# colunas não gera linha, porque antes e depois ficam iguais depois do recorte.
CRIAR_FUNCAO = """
CREATE OR REPLACE FUNCTION registrar_auditoria() RETURNS trigger AS $$
DECLARE
    ocultas TEXT[] := ARRAY['senha_hash', 'token_hash', 'token', 'endpoint', 'p256dh', 'auth'];
    antes JSONB;
    depois JSONB;
    linha JSONB;
    registro TEXT;
    dono UUID;
    correlacao TEXT;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        antes := to_jsonb(OLD) - ocultas;
    END IF;
    IF TG_OP <> 'DELETE' THEN
        depois := to_jsonb(NEW) - ocultas;
    END IF;
    IF TG_OP = 'UPDATE' AND antes = depois THEN
        RETURN NULL;
    END IF;
    linha := COALESCE(depois, antes);
    registro := linha->>'id';
    dono := (CASE WHEN TG_TABLE_NAME = 'usuarios' THEN registro ELSE linha->>'usuario_id' END)::uuid;
    correlacao := NULLIF(current_setting('app.correlation_id', true), '');
    INSERT INTO auditoria (
        tabela, operacao, registro_id, usuario_id, correlation_id, dados_antes, dados_depois
    ) VALUES (TG_TABLE_NAME, TG_OP, registro, dono, correlacao, antes, depois);
    RAISE LOG 'auditoria tabela=% operacao=% registro_id=% usuario_id=% correlation_id=%',
        TG_TABLE_NAME, TG_OP, registro, dono, correlacao;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def comandos_upgrade() -> list[str]:
    triggers = [
        f"CREATE TRIGGER auditoria_{tabela} AFTER INSERT OR UPDATE OR DELETE ON {tabela} "
        "FOR EACH ROW EXECUTE FUNCTION registrar_auditoria();"
        for tabela in TABELAS_AUDITADAS
    ]
    return [CRIAR_TABELA, CRIAR_FUNCAO, *triggers]


def upgrade() -> None:
    for comando in comandos_upgrade():
        op.execute(comando)


def downgrade() -> None:
    for tabela in TABELAS_AUDITADAS:
        op.execute(f"DROP TRIGGER IF EXISTS auditoria_{tabela} ON {tabela};")
    op.execute("DROP FUNCTION IF EXISTS registrar_auditoria();")
    op.execute("DROP TABLE IF EXISTS auditoria;")
