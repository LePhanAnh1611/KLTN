"""add word_set_ratings + reports (UC-23, UC-24)

Revision ID: b2d3e4f5m6s2
Revises: a1c41f0daily
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d3e4f5m6s2'
down_revision: Union[str, Sequence[str], None] = 'a1c41f0daily'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'word_set_ratings',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('word_set_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('stars', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['word_set_id'], ['word_sets.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('word_set_id', 'user_id', name='uq_word_set_rating'),
    )
    op.create_index(op.f('ix_word_set_ratings_word_set_id'), 'word_set_ratings', ['word_set_id'], unique=False)
    op.create_index(op.f('ix_word_set_ratings_user_id'), 'word_set_ratings', ['user_id'], unique=False)

    op.create_table(
        'reports',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('reporter_id', sa.BigInteger(), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_id', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reports_reporter_id'), 'reports', ['reporter_id'], unique=False)
    op.create_index(op.f('ix_reports_target_id'), 'reports', ['target_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_reports_target_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_reporter_id'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_word_set_ratings_user_id'), table_name='word_set_ratings')
    op.drop_index(op.f('ix_word_set_ratings_word_set_id'), table_name='word_set_ratings')
    op.drop_table('word_set_ratings')
