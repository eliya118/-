"""google calendar link"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_google"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("family", sa.Column("google_refresh_token", sa.Text(), nullable=True))
    op.add_column("event", sa.Column("google_event_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("event", "google_event_id")
    op.drop_column("family", "google_refresh_token")
