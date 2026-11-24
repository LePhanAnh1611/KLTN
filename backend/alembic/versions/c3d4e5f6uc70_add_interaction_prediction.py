"""UC-70: ghi du doan cua mo hinh TRUOC khi thay ket qua (do prequential)

Revision ID: c3d4e5f6uc70
Revises: b2c3d4e5uc88
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6uc70'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5uc88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # P(tra loi dung) ma he thong NAM GIU NGAY TRUOC khi thay ket qua luot nay.
    # Khong co cot nay thi khong the do hieu nang mo hinh mot cach trung thuc:
    # so sanh mastery HIEN TAI (da bi chinh luot do cap nhat) voi ket qua luot do
    # la vong lap tu chung minh.
    op.add_column('interactions', sa.Column('predicted_mastery', sa.Float(), nullable=True))
    # NULL mang y nghia rieng: "chua co du doan nao" (lan dau gap tu, hoac mo hinh
    # khong biet tu do) — phai phan biet duoc voi mot du doan bang 0.5.
    op.add_column(
        'interactions',
        sa.Column('prediction_source', sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('interactions', 'prediction_source')
    op.drop_column('interactions', 'predicted_mastery')
