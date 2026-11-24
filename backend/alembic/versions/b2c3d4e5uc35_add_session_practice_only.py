"""add sessions.practice_only (UC-35 luyện thường không ảnh hưởng lịch ôn)

Revision ID: b2c3d4e5uc35
Revises: a1b2c3d4uc85
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5uc35'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4uc85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'sessions',
        sa.Column('practice_only', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sessions', 'practice_only')
