"""Cờ loại trừ cho Interaction (interactions.excluded_reason).

Sự cố 2026-10-26: phương án trắc nghiệm đổi sang hiện nghĩa chính nhưng server
vẫn chấm theo nghĩa đầy đủ, nên mọi lượt chọn nghĩa của từ nhiều nghĩa bị ghi
sai. Đáp án gốc không được lưu nên không chấm lại được — các lượt đó được đánh
dấu loại trừ thay vì xóa (BR-05: giữ toàn vẹn lịch sử, truy vết được).
NULL = lượt hợp lệ.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6excl"
down_revision = "a2b3c4d5exvi"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interactions", sa.Column("excluded_reason", sa.String(length=40), nullable=True))


def downgrade():
    op.drop_column("interactions", "excluded_reason")
