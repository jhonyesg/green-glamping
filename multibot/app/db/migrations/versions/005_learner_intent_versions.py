"""Add learner_proposals and intent_versions tables.

Revision ID: 005
Revises: 004

Agrega al schema public:
- learner_proposals: propuestas auto-generadas por el learner
  para crear/actualizar/deprecar intents. Admin revisa en
  /admin/learner.
- intent_versions: snapshots del estado completo de un intent
  en cada cambio. Permite rollback y auditoría.

Idempotente: usa CREATE TABLE IF NOT EXISTS y el modelo
declara los enums con `native_enum=False` para que la migración
no falle si los enums ya existen.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # learner_proposals (idempotente: IF NOT EXISTS)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learner_proposals (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            kind VARCHAR(30) NOT NULL,
            payload JSONB NOT NULL,
            sample_messages JSONB,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            confidence DOUBLE PRECISION,
            source_message_hash VARCHAR(64),
            proposed_at TIMESTAMPTZ DEFAULT NOW(),
            reviewed_at TIMESTAMPTZ,
            reviewed_by VARCHAR(100),
            CHECK (kind IN ('create_intent', 'update_intent', 'deprecate_intent')),
            CHECK (status IN ('pending', 'accepted', 'rejected', 'applied', 'applied_edited'))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_learner_proposals_tenant_status
        ON learner_proposals (tenant_id, status)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_learner_proposals_hash
        ON learner_proposals (source_message_hash)
    """)

    # intent_versions (idempotente)
    op.execute("""
        CREATE TABLE IF NOT EXISTS intent_versions (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            intent_id INTEGER,
            intent_name VARCHAR(100) NOT NULL,
            snapshot JSONB NOT NULL,
            source VARCHAR(30) NOT NULL DEFAULT 'manual',
            reverted_from INTEGER,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CHECK (source IN ('seed', 'manual', 'auto_learner', 'revert'))
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_intent_versions_tenant_intent
        ON intent_versions (tenant_id, intent_id)
    """)
    # FK self-referencial (creada con ALTER después para evitar
    # problemas de orden de creación en IF NOT EXISTS)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_intent_version_reverted_from'
                  AND table_name = 'intent_versions'
            ) THEN
                ALTER TABLE public.intent_versions
                ADD CONSTRAINT fk_intent_version_reverted_from
                FOREIGN KEY (reverted_from)
                REFERENCES public.intent_versions(id) ON DELETE SET NULL;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_intent_versions_tenant_intent")
    op.execute("DROP TABLE IF EXISTS intent_versions CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_learner_proposals_hash")
    op.execute("DROP INDEX IF EXISTS ix_learner_proposals_tenant_status")
    op.execute("DROP TABLE IF EXISTS learner_proposals CASCADE")
