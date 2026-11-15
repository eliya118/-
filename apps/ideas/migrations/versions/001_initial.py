"""ideas cache"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "suggestion_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("age_band", sa.String(16), nullable=False),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("slot", sa.String(16), nullable=False),
        sa.Column("iso_week", sa.String(16), nullable=False),
        sa.Column("day_context", sa.String(16), nullable=False),
        sa.Column("catalog_version", sa.String(16), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "kind",
            "age_band",
            "locale",
            "slot",
            "iso_week",
            "day_context",
            "catalog_version",
            name="uq_suggestion_cache_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("suggestion_cache")
