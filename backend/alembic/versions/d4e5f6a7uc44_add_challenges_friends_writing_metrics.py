"""add challenge_claims (UC-44), friendships (UC-56), pronunciation_attempts,
model_metrics (UC-70), writing_submissions + sentence_notes (UC-37, UC-38)

Revision ID: d4e5f6a7uc44
Revises: c3d4e5f6uc12
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7uc44'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6uc12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TIMESTAMPS = (
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
)


def upgrade() -> None:
    """Upgrade schema."""
    # ---- UC-44 thử thách hôm nay ----
    op.create_table(
        'challenge_claims',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('challenge_date', sa.Date(), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('xp_awarded', sa.Integer(), nullable=False),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'challenge_date', 'code', name='uq_claim_user_date_code'),
    )
    op.create_index(op.f('ix_challenge_claims_user_id'), 'challenge_claims', ['user_id'])
    op.create_index(op.f('ix_challenge_claims_challenge_date'), 'challenge_claims',
                    ['challenge_date'])

    # ---- UC-56 kết bạn ----
    op.create_table(
        'friendships',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('requester_id', sa.BigInteger(), nullable=False),
        sa.Column('addressee_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['addressee_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('requester_id', 'addressee_id', name='uq_friendship_pair'),
    )
    op.create_index(op.f('ix_friendships_requester_id'), 'friendships', ['requester_id'])
    op.create_index(op.f('ix_friendships_addressee_id'), 'friendships', ['addressee_id'])
    op.create_index(op.f('ix_friendships_status'), 'friendships', ['status'])

    # ---- lưu kết quả luyện phát âm ----
    op.create_table(
        'pronunciation_attempts',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('item_id', sa.BigInteger(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('transcript', sa.String(length=300), nullable=True),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pronunciation_attempts_user_id'), 'pronunciation_attempts',
                    ['user_id'])
    op.create_index(op.f('ix_pronunciation_attempts_item_id'), 'pronunciation_attempts',
                    ['item_id'])

    # ---- UC-70 giám sát mô hình ----
    op.create_table(
        'model_metrics',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('model_name', sa.String(length=50), nullable=False),
        sa.Column('metric', sa.String(length=30), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_model_metrics_model_name'), 'model_metrics', ['model_name'])
    op.create_index(op.f('ix_model_metrics_recorded_at'), 'model_metrics', ['recorded_at'])

    # ---- UC-37 luyện viết · UC-38 sổ tay câu ----
    op.create_table(
        'writing_submissions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('prompt_vi', sa.Text(), nullable=False),
        sa.Column('answer_en', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('suggestion', sa.Text(), nullable=True),
        sa.Column('grader', sa.String(length=20), nullable=False),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_writing_submissions_user_id'), 'writing_submissions', ['user_id'])

    op.create_table(
        'sentence_notes',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('text_en', sa.Text(), nullable=False),
        sa.Column('text_vi', sa.Text(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('submission_id', sa.BigInteger(), nullable=True),
        *_TIMESTAMPS,
        sa.ForeignKeyConstraint(['submission_id'], ['writing_submissions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sentence_notes_user_id'), 'sentence_notes', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_sentence_notes_user_id'), table_name='sentence_notes')
    op.drop_table('sentence_notes')
    op.drop_index(op.f('ix_writing_submissions_user_id'), table_name='writing_submissions')
    op.drop_table('writing_submissions')

    op.drop_index(op.f('ix_model_metrics_recorded_at'), table_name='model_metrics')
    op.drop_index(op.f('ix_model_metrics_model_name'), table_name='model_metrics')
    op.drop_table('model_metrics')

    op.drop_index(op.f('ix_pronunciation_attempts_item_id'), table_name='pronunciation_attempts')
    op.drop_index(op.f('ix_pronunciation_attempts_user_id'), table_name='pronunciation_attempts')
    op.drop_table('pronunciation_attempts')

    op.drop_index(op.f('ix_friendships_status'), table_name='friendships')
    op.drop_index(op.f('ix_friendships_addressee_id'), table_name='friendships')
    op.drop_index(op.f('ix_friendships_requester_id'), table_name='friendships')
    op.drop_table('friendships')

    op.drop_index(op.f('ix_challenge_claims_challenge_date'), table_name='challenge_claims')
    op.drop_index(op.f('ix_challenge_claims_user_id'), table_name='challenge_claims')
    op.drop_table('challenge_claims')
