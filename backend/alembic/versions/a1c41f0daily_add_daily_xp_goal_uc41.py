"""add daily_xp_goal to user_settings (UC-41)

Revision ID: a1c41f0daily
Revises: 8eb8cf8dd4b7
Create Date: 2026-07-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c41f0daily'
down_revision: Union[str, Sequence[str], None] = '8eb8cf8dd4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('daily_xp_goal', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_settings', 'daily_xp_goal')
