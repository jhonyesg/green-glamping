"""Tenant-scoped tables: offering and media.

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

Las tablas se crean en cada schema de tenant existente.
Para tenants nuevos, el seeder debe crearlas en su schema.

Crea:
- <tenant_schema>.offering (catálogo de planes/servicios)
- <tenant_schema>.media (biblioteca de archivos)

Eliminación: downgrade() dropea las tablas en todos los schemas de
tenants activos + el cascade a offering.imagen_id.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
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

    # Enums a nivel de public (se referencian desde cada tenant)
    offering_source = sa.Enum("seed", "manual", "auto_learner", name="offering_source")
    offering_source.create(conn, checkfirst=True)
    media_type = sa.Enum("image", "audio", "document", name="media_type")
    media_type.create(conn, checkfirst=True)
    media_source = sa.Enum("seed", "uploaded", name="media_source")
    media_source.create(conn, checkfirst=True)

    for schema in schemas:
        # offering
        op.create_table(
            "offering",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(100), nullable=False),
            sa.Column("nombre", sa.String(200), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=True),
            sa.Column("precio_cop", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("incluye", JSONB(), nullable=False, server_default="[]"),
            sa.Column("imagen_id", sa.Integer(), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "source",
                offering_source,
                nullable=False,
                server_default="seed",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id", name="pk_offering"),
            sa.UniqueConstraint("slug", name="uq_offering_slug"),
            schema=schema,
        )
        op.create_index("ix_offering_slug", "offering", ["slug"], schema=schema)

        # media
        op.create_table(
            "media",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(150), nullable=False),
            sa.Column("tipo", media_type, nullable=False),
            sa.Column("path", sa.String(500), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("original_filename", sa.String(300), nullable=True),
            sa.Column("original_path", sa.String(500), nullable=True),
            sa.Column("descripcion", sa.String(500), nullable=True),
            sa.Column("uploaded_by", sa.String(100), nullable=True),
            sa.Column("source", media_source, nullable=False, server_default="uploaded"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("id", name="pk_media"),
            sa.UniqueConstraint("key", name="uq_media_key"),
            schema=schema,
        )
        op.create_index("ix_media_key", "media", ["key"], schema=schema)

        # FK de offering.imagen_id → media.id (dentro del mismo schema del tenant)
        op.create_foreign_key(
            "fk_offering_imagen_id_media",
            "offering", "media",
            ["imagen_id"], ["id"],
            source_schema=schema, referent_schema=schema,
            ondelete="SET NULL",
        )


def downgrade() -> None:
    conn = op.get_bind()
    schemas = _existing_tenant_schemas(conn)
    for schema in schemas:
        op.drop_constraint(
            "fk_offering_imagen_id_media", "offering",
            schema=schema,
        )
        op.drop_index("ix_media_key", table_name="media", schema=schema)
        op.drop_table("media", schema=schema)
        op.drop_index("ix_offering_slug", table_name="offering", schema=schema)
        op.drop_table("offering", schema=schema)
    op.execute("DROP TYPE IF EXISTS media_source")
    op.execute("DROP TYPE IF EXISTS media_type")
    op.execute("DROP TYPE IF EXISTS offering_source")
