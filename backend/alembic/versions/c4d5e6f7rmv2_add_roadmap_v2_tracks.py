"""Lộ trình v2: hai track (chủ đề + cốt lõi) song song với lộ trình v1.

- learning_stages.roadmap_version: mọi chặng hiện có = 1 (server_default).
- learning_stages.track / topic: chỉ dùng cho chặng v2.
- users.roadmap_version: MỌI tài khoản đang có = 1, để học viên pilot tiếp tục
  đúng bản đồ cũ (bản sao, Interaction, KNOWLEDGE_STATE không đổi một dòng nào);
  sau migration mặc định đổi sang 2 cho tài khoản tạo mới.

Chỉ THÊM cột — không xóa/sửa dữ liệu nào đang có.
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7rmv2"
down_revision = "b3c4d5e6excl"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("learning_stages", sa.Column(
        "roadmap_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("learning_stages", sa.Column("track", sa.String(length=20), nullable=True))
    op.add_column("learning_stages", sa.Column("topic", sa.String(length=100), nullable=True))
    op.create_index("ix_learning_stages_roadmap_version", "learning_stages", ["roadmap_version"])

    # Tài khoản hiện có -> 1 (server_default điền sẵn cho các dòng cũ) ...
    op.add_column("users", sa.Column(
        "roadmap_version", sa.Integer(), nullable=False, server_default="1"))
    # ... rồi tài khoản tạo SAU migration mới mặc định 2.
    op.alter_column("users", "roadmap_version", server_default="2")


def downgrade():
    op.drop_column("users", "roadmap_version")
    op.drop_index("ix_learning_stages_roadmap_version", table_name="learning_stages")
    op.drop_column("learning_stages", "topic")
    op.drop_column("learning_stages", "track")
    op.drop_column("learning_stages", "roadmap_version")
