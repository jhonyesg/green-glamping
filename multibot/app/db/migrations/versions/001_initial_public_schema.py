"""Initial public schema: plans and tenants.

Revision ID: 001
Revises:
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS public")

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_concurrent_chats", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("channels_included", JSONB(), nullable=False, server_default="{}"),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("llm_tokens_included", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id", name="pk_plans"),
        sa.UniqueConstraint("name", name="uq_plans_name"),
        schema="public",
    )

    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column(
            "operation_mode",
            sa.Enum("autonomous", "assisted", "hybrid", name="operationmode", schema="public"),
            nullable=False,
            server_default="hybrid",
        ),
        sa.Column(
            "status",
            sa.Enum("provisioning", "active", "suspended", "archived", name="tenantstatus", schema="public"),
            nullable=False,
            server_default="provisioning",
        ),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("payment_message_template", JSONB(), nullable=False, server_default="{}"),
        sa.Column("welcome_variant", sa.String(50), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("contact_info", JSONB(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["public.plans.id"], name="fk_tenants_plan_id_plans"),
        sa.PrimaryKeyConstraint("id", name="pk_tenants"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        schema="public",
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], schema="public")

    # Seed a default plan
    op.execute(
        "INSERT INTO public.plans (name, max_concurrent_chats, monthly_price) "
        "VALUES ('starter', 50, 0) ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_slug", table_name="tenants", schema="public")
    op.drop_table("tenants", schema="public")
    op.drop_table("plans", schema="public")
    op.execute("DROP TYPE IF EXISTS public.operationmode")
    op.execute("DROP TYPE IF EXISTS public.tenantstatus")
