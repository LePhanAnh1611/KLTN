"""UC-87: ghi nguon goc cua bo tu (thu cong / PDF / CSV / tai ve)

Revision ID: a1b2c3d4uc87
Revises: f6a7b8c9spk2
Create Date: 2026-08-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4uc87'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9spk2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default='manual' để mọi bộ từ đã có (đều do người dùng tự tạo hoặc
    # tải về) có giá trị đúng mà không cần backfill riêng.
    op.add_column(
        'word_sets',
        sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
    )
    op.add_column('word_sets', sa.Column('source_filename', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('word_sets', 'source_filename')
    op.drop_column('word_sets', 'source')
