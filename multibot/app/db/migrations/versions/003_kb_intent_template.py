"""Extend kb_intents with templating fields.

Revision ID: 003
Revises: 002

Agrega a kb_intents (en cada schema de tenant):
- response_type: 'static' (default) | 'template_jinja' | 'data_driven'
- response_template: text con template Jinja (nullable)
- requires_data: jsonb lista de claves requeridas (para data_driven)
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def _existing_tenant_schemas(conn) -> list[str]:
    rows = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'tenant_%'"
        )
    ).fetchall()
    return [r[0] for r in rows]


def upgrade() -> None:
    conn = op.get_bind()
    schemas = _existing_tenant_schemas(conn)

    for schema in schemas:
        op.add_column(
            "kb_intents",
            sa.Column(
                "response_type",
                sa.String(20),
                nullable=False,
                server_default="static",
            ),
            schema=schema,
        )
        op.add_column(
            "kb_intents",
            sa.Column("response_template", sa.Text(), nullable=True),
            schema=schema,
        )
        op.add_column(
            "kb_intents",
            sa.Column("requires_data", JSONB(), nullable=True),
            schema=schema,
        )


def downgrade() -> None:
    conn = op.get_bind()
    schemas = _existing_tenant_schemas(conn)
    for schema in schemas:
        op.drop_column("kb_intents", "requires_data", schema=schema)
        op.drop_column("kb_intents", "response_template", schema=schema)
        op.drop_column("kb_intents", "response_type", schema=schema)
