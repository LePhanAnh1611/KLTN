"""UC-88: mui gio cua nguoi hoc (ngay "hom nay" khong con tinh theo UTC)

Revision ID: b2c3d4e5uc88
Revises: a1b2c3d4uc87
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5uc88'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4uc87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default là giờ Việt Nam chứ KHÔNG phải UTC: sản phẩm phục vụ người
    # học Việt, và tài khoản đã có từ trước cũng phải được tính ngày cho đúng.
    op.add_column(
        'user_settings',
        sa.Column('timezone', sa.String(length=64),
                  server_default='Asia/Ho_Chi_Minh', nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_settings', 'timezone')
