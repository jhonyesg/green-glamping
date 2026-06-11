"""CLI to provision a new tenant: create schema + run tenant migrations + insert row."""

import argparse
import asyncio

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
import app.models.plan  # noqa: F401 - needed for FK resolution
from app.models.tenant import Tenant, TenantStatus, OperationMode


TENANT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    type VARCHAR(40) NOT NULL,
    credentials JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT FALSE,
    webhook_url VARCHAR(500),
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS llm_providers (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    provider_name VARCHAR(100) NOT NULL,
    model VARCHAR(200) NOT NULL,
    api_key VARCHAR(2000),
    base_url VARCHAR(500),
    capabilities JSONB DEFAULT '{}',
    stt_fallback JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_intents (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    intent_name VARCHAR(200) NOT NULL,
    keywords_regex TEXT NOT NULL,
    response_text TEXT NOT NULL,
    response_audio_id INTEGER,
    response_image_ids JSONB DEFAULT '[]',
    handoff_rule VARCHAR(20),
    requires_human BOOLEAN DEFAULT FALSE,
    human_reason TEXT,
    priority INTEGER DEFAULT 0,
    status VARCHAR(30) DEFAULT 'active',
    source VARCHAR(30) DEFAULT 'seed',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS handoff_rules (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL,
    rule_code VARCHAR(20) NOT NULL,
    trigger_intent VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    notify_channel VARCHAR(40),
    notify_target VARCHAR(200),
    custom_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    channel_id INTEGER,
    external_thread_id VARCHAR(200) NOT NULL,
    user_external_id VARCHAR(200),
    push_name VARCHAR(200),
    operation_mode_snapshot VARCHAR(20) DEFAULT 'hybrid',
    state VARCHAR(40) DEFAULT 'active',
    in_handoff BOOLEAN DEFAULT FALSE,
    handoff_at TIMESTAMPTZ,
    handoff_rule VARCHAR(20),
    handoff_expires_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    last_responder VARCHAR(10) DEFAULT 'bot',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, external_thread_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,
    content_type VARCHAR(20) DEFAULT 'text',
    content_text TEXT,
    intent_id INTEGER,
    matched_via VARCHAR(20) DEFAULT 'regex',
    llm_tokens_used INTEGER DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    feedback VARCHAR(10) DEFAULT 'none',
    feedback_note TEXT,
    ts TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_ts ON messages (conversation_id, ts);

CREATE TABLE IF NOT EXISTS message_attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    file_type VARCHAR(20),
    file_path VARCHAR(500),
    original_filename VARCHAR(200),
    mime_type VARCHAR(100),
    size_bytes INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS handoff_events (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    rule_code VARCHAR(20),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    context_snapshot JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS reservations (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    tenant_id INTEGER NOT NULL,
    guest_name VARCHAR(200),
    guest_id_number VARCHAR(50),
    check_in DATE,
    check_out DATE,
    combo VARCHAR(100),
    guests_count INTEGER DEFAULT 1,
    total_price NUMERIC(10, 2),
    state VARCHAR(40) DEFAULT 'tentative',
    payment_proof_path VARCHAR(500),
    confirmed_by VARCHAR(200),
    confirmed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS availability_sources (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    source_type VARCHAR(40) NOT NULL,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS media_assets (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    asset_type VARCHAR(40),
    file_path VARCHAR(500),
    original_filename VARCHAR(200),
    mime_type VARCHAR(100),
    size_bytes INTEGER,
    use_count INTEGER DEFAULT 0,
    is_pregenerated BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    quarantined_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback_tickets (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    conversation_id INTEGER REFERENCES conversations(id),
    message_id INTEGER REFERENCES messages(id),
    ticket_type VARCHAR(40),
    original_text TEXT,
    suggested_response TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_by VARCHAR(200),
    reviewed_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    action VARCHAR(100),
    entity_type VARCHAR(50),
    entity_id INTEGER,
    performed_by VARCHAR(200),
    details JSONB DEFAULT '{}',
    ts TIMESTAMPTZ DEFAULT NOW()
);
"""


async def create_tenant(slug: str, plan_id: int, name: str, mode: str) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    schema_name = f"tenant_{slug}"

    async with session_factory() as session:
        # Create schema
        await session.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        await session.commit()

        # Run tenant tables in the new schema
        await session.execute(sa.text(f'SET search_path TO "{schema_name}", public'))
        for statement in TENANT_TABLES_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                await session.execute(sa.text(statement))
        await session.commit()

        # Reset search path and check if tenant already exists
        await session.execute(sa.text("SET search_path TO public"))
        existing = await session.execute(
            sa.select(Tenant).where(Tenant.slug == slug)
        )
        if existing.scalar_one_or_none():
            print(f"Tenant '{slug}' already exists.")
            await engine.dispose()
            return -1

        # Create public.tenants row
        tenant = Tenant(
            name=name,
            slug=slug,
            operation_mode=OperationMode(mode),
            status=TenantStatus.active,
            plan_id=plan_id if plan_id > 0 else None,
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        print(f"Tenant '{slug}' created with ID={tenant.id}, schema='{schema_name}'")
        await engine.dispose()
        return tenant.id


def main():
    parser = argparse.ArgumentParser(description="Create a new Multibot tenant")
    parser.add_argument("--slug", required=True, help="Unique slug (e.g. 'demo')")
    parser.add_argument("--name", default=None, help="Display name (defaults to slug)")
    parser.add_argument("--plan-id", type=int, default=0, help="Plan ID (0 = no plan)")
    parser.add_argument("--mode", default="hybrid", choices=["autonomous", "assisted", "hybrid"])
    args = parser.parse_args()
    asyncio.run(create_tenant(args.slug, args.plan_id, args.name or args.slug, args.mode))


if __name__ == "__main__":
    main()
