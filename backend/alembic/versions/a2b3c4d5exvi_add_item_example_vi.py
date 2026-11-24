"""Bản dịch tiếng Việt của câu ví dụ (items.example_vi).

Bộ nền đã có sẵn bản dịch cho mọi câu ví dụ (FVDP kèm bản dịch, câu LLM sinh
kèm bản dịch) nhưng trước đây bị bỏ khi seed. Để NULL được: bộ chủ đề và từ người
học tự nhập không có bản dịch. Dữ liệu cũ điền bằng
`python -m app.scripts.sync_seed_content --apply`.
"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5exvi"
down_revision = "f1a2b3c4plt"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("items", sa.Column("example_vi", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("items", "example_vi")
