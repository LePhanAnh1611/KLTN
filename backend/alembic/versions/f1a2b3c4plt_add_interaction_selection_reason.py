"""Pilot — ghi LÝ DO từ được đưa ra cho người học (selection_reason).

Phục vụ kiểm chứng DKT trên người dùng thật: 'band' = gợi ý vừa sức (BR-03),
'explore' = chọn ngẫu nhiên để thăm dò (không phụ thuộc dự đoán của mô hình),
'review' = đến lịch ôn, 'validation' = bài kiểm tra cuối. Chỉ số đo trên lượt
'explore'/'validation' không bị thiên lệch chọn mẫu, vì mô hình không tự chọn
dữ liệu để chấm chính nó.
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4plt"
down_revision = "e1f2a3b4rvw"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interactions", sa.Column("selection_reason", sa.String(length=12), nullable=True))


def downgrade():
    op.drop_column("interactions", "selection_reason")
