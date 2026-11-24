"""Allow learners to pause reviews without changing mastery."""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4rvw"
down_revision = "d0e1f2a3cefr"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("review_schedules", sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("review_schedules", "is_paused")
