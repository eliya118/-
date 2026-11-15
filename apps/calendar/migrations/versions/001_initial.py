"""calendar schema"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "family",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(2), nullable=False),
    )
    op.create_table(
        "parent_account",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("family.id"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
    )
    op.create_table(
        "session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("family.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "child",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("family.id"), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=False),
        sa.Column("birth_month", sa.Integer(), nullable=False),
    )
    op.create_table(
        "event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("family.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("locale", sa.String(2), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_event_family_starts", "event", ["family_id", "starts_at"])
    op.create_table(
        "event_child",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("event.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("child.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_outbox_unpublished", "outbox", ["published_at"])
    op.create_table(
        "idempotency",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_table("outbox")
    op.drop_table("event_child")
    op.drop_table("event")
    op.drop_table("child")
    op.drop_table("session")
    op.drop_table("parent_account")
    op.drop_table("family")
