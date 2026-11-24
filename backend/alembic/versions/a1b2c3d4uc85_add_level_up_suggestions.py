"""add level_up_suggestions (UC-85 nâng cấp trình độ)

Revision ID: a1b2c3d4uc85
Revises: e1a2b3c4uc03
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4uc85'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4uc03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'level_up_suggestions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('from_level', sa.String(length=5), nullable=False),
        sa.Column('to_level', sa.String(length=5), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('avg_mastery', sa.Float(), nullable=False),
        sa.Column('items_considered', sa.Integer(), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_level_up_suggestions_user_id'), 'level_up_suggestions',
                    ['user_id'], unique=False)
    op.create_index(op.f('ix_level_up_suggestions_status'), 'level_up_suggestions',
                    ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_level_up_suggestions_status'), table_name='level_up_suggestions')
    op.drop_index(op.f('ix_level_up_suggestions_user_id'), table_name='level_up_suggestions')
    op.drop_table('level_up_suggestions')
