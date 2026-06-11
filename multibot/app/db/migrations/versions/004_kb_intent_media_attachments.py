"""Add response_media_ids (jsonb) to kb_intents + backfill from response_audio_id.

Revision ID: 004
Revises: 003

Agrega a kb_intents (en cada schema de tenant):
- response_media_ids: jsonb, default '[]', lista de ids de media a adjuntar
  cuando el intent matchea. Backfill: si response_audio_id está set,
  se agrega al array.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
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
                "response_media_ids",
                JSONB(),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            schema=schema,
        )
        # Backfill: copiar response_audio_id a response_media_ids
        op.execute(
            sa.text(
                f'UPDATE "{schema}".kb_intents '
                "SET response_media_ids = jsonb_build_array(response_audio_id) "
                "WHERE response_audio_id IS NOT NULL"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    schemas = _existing_tenant_schemas(conn)
    for schema in schemas:
        op.drop_column("kb_intents", "response_media_ids", schema=schema)
