"""add placement (UC-11) + learning_stages (UC-84)

Revision ID: d0f1a2b3uc84
Revises: c9e0f1a2m7s8
Create Date: 2026-07-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0f1a2b3uc84'
down_revision: Union[str, Sequence[str], None] = 'c9e0f1a2m7s8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'placement_questions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('cefr_level', sa.String(length=5), nullable=False),
        sa.Column('word', sa.String(length=200), nullable=False),
        sa.Column('correct_meaning', sa.String(length=300), nullable=False),
        sa.Column('distractors', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_placement_questions_cefr_level'), 'placement_questions',
                    ['cefr_level'], unique=False)

    op.create_table(
        'placement_attempts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='completed', nullable=False),
        sa.Column('answered_count', sa.Integer(), nullable=False),
        sa.Column('correct_count', sa.Integer(), nullable=False),
        sa.Column('per_level', sa.JSON(), nullable=False),
        sa.Column('estimated_level', sa.String(length=5), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_placement_attempts_user_id'), 'placement_attempts',
                    ['user_id'], unique=False)

    op.add_column('user_settings', sa.Column('entry_cefr_level', sa.String(length=5), nullable=True))

    op.create_table(
        'learning_stages',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('cefr_level', sa.String(length=5), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('word_set_id', sa.BigInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['word_set_id'], ['word_sets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_learning_stages_cefr_level'), 'learning_stages',
                    ['cefr_level'], unique=False)
    op.create_index(op.f('ix_learning_stages_word_set_id'), 'learning_stages',
                    ['word_set_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_learning_stages_word_set_id'), table_name='learning_stages')
    op.drop_index(op.f('ix_learning_stages_cefr_level'), table_name='learning_stages')
    op.drop_table('learning_stages')

    op.drop_column('user_settings', 'entry_cefr_level')

    op.drop_index(op.f('ix_placement_attempts_user_id'), table_name='placement_attempts')
    op.drop_table('placement_attempts')
    op.drop_index(op.f('ix_placement_questions_cefr_level'), table_name='placement_questions')
    op.drop_table('placement_questions')
