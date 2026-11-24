"""UC-96 — nhan (tag) cho bo tu vung

Vi sao them bang rieng chu khong nhoi vao mot cot chuoi: nhan phai LOC va DEM
duoc ("con bao nhieu bo mang #ielts"). Nhoi vao mot cot roi LIKE '%ielts%' se
khop ca '#ielts-writing' lan '#no-ielts', va khong the dem chinh xac.

Khac `category` (UC-76, danh muc do Admin quan ly, moi bo mot danh muc): nhan la
lop LOC CHEO, nguoi tao bo tu tu dat, mot bo nhieu nhan.

Revision ID: e5f6a7b8uc96
Revises: d4e5f6a7uc66
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8uc96"
down_revision = "d4e5f6a7uc66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "word_set_tags",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "word_set_id", sa.BigInteger(),
            sa.ForeignKey("word_sets.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("tag", sa.String(40), nullable=False),
        sa.UniqueConstraint("word_set_id", "tag", name="uq_word_set_tag"),
    )
    # Loc theo nhan la truy van chinh cua trang Kham pha -> phai co index.
    op.create_index("ix_word_set_tags_tag", "word_set_tags", ["tag"])
    op.create_index("ix_word_set_tags_word_set_id", "word_set_tags", ["word_set_id"])


def downgrade() -> None:
    op.drop_index("ix_word_set_tags_word_set_id", table_name="word_set_tags")
    op.drop_index("ix_word_set_tags_tag", table_name="word_set_tags")
    op.drop_table("word_set_tags")
