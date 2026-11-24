"""gộp luyện từ & đọc câu mẫu vào pronunciation_attempts

Revision ID: f6a7b8c9spk2
Revises: e5f6a7b8spk
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9spk2'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8spk'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default='word' để các bản ghi cũ (đều là luyện từ) tự có giá trị đúng
    op.add_column(
        'pronunciation_attempts',
        sa.Column('kind', sa.String(length=20), server_default='word', nullable=False),
    )
    op.add_column('pronunciation_attempts', sa.Column('target_text', sa.Text(), nullable=True))
    op.add_column('pronunciation_attempts', sa.Column('detail', sa.JSON(), nullable=True))
    op.create_index(op.f('ix_pronunciation_attempts_kind'), 'pronunciation_attempts', ['kind'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_pronunciation_attempts_kind'), table_name='pronunciation_attempts')
    op.drop_column('pronunciation_attempts', 'detail')
    op.drop_column('pronunciation_attempts', 'target_text')
    op.drop_column('pronunciation_attempts', 'kind')
