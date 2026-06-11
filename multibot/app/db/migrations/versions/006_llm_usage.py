"""Add public.llm_usage table for tracking LLM provider usage.

Revision ID: 006
Revises: 005

Una fila por cada llamada al LLM. Registra:
- tenant_id: a quién le cobramos
- provider_id: qué provider atendió
- conversation_id: para análisis por conversación
- latency_ms: tiempo de respuesta
- tokens_used: total tokens consumidos
- cost_usd: costo estimado (calculado en Python)
- bypassed: true si fue regex_bypass (no LLM call, pero
  igual registramos para métricas de bypass)
- created_at: timestamp

Idempotente: usa IF NOT EXISTS.
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            -- provider_id NO tiene FK: cada tenant tiene sus
            -- llm_providers en su propio schema, no en public.
            -- La integridad referencial se valida en Python al
            -- insertar (o se acepta que apunte a un id que no
            -- existe más, simplemente contando como orphaned).
            provider_id INTEGER,
            conversation_id INTEGER,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            tokens_used INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
            bypassed BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CHECK (bypassed = false OR (tokens_used = 0 AND cost_usd = 0))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_llm_usage_tenant_created
        ON llm_usage (tenant_id, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_llm_usage_provider_created
        ON llm_usage (provider_id, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_llm_usage_provider_created")
    op.execute("DROP INDEX IF EXISTS ix_llm_usage_tenant_created")
    op.execute("DROP TABLE IF EXISTS llm_usage CASCADE")
