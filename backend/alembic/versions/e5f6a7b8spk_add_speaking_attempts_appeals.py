"""add speaking_attempts + speaking_appeals (module luyện nói)

Revision ID: e5f6a7b8spk
Revises: d4e5f6a7uc44
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8spk'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7uc44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIMESTAMPS = (
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'speaking_attempts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('task_prompt', sa.Text(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('overall_level', sa.Integer(), nullable=False),
        sa.Column('scores', sa.JSON(), nullable=False),
        sa.Column('audio_metrics', sa.JSON(), nullable=False),
        sa.Column('developmental_feedback', sa.Text(), nullable=False),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.Column('rubric_version', sa.String(length=20), nullable=False),
        sa.Column('words_per_minute', sa.Float(), nullable=False),
        sa.Column('asr_avg_confidence', sa.Float(), nullable=False),
        sa.Column('duration_sec', sa.Float(), nullable=False),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_speaking_attempts_user_id'), 'speaking_attempts', ['user_id'])

    op.create_table(
        'speaking_appeals',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('attempt_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('criterion', sa.String(length=30), nullable=False),
        sa.Column('expected_level', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['attempt_id'], ['speaking_attempts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_speaking_appeals_attempt_id'), 'speaking_appeals', ['attempt_id'])
    op.create_index(op.f('ix_speaking_appeals_user_id'), 'speaking_appeals', ['user_id'])
    op.create_index(op.f('ix_speaking_appeals_status'), 'speaking_appeals', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_speaking_appeals_status'), table_name='speaking_appeals')
    op.drop_index(op.f('ix_speaking_appeals_user_id'), table_name='speaking_appeals')
    op.drop_index(op.f('ix_speaking_appeals_attempt_id'), table_name='speaking_appeals')
    op.drop_table('speaking_appeals')

    op.drop_index(op.f('ix_speaking_attempts_user_id'), table_name='speaking_attempts')
    op.drop_table('speaking_attempts')
