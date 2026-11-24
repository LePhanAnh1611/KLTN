"""Nguon goc nghia & cau vi du cua ITEM (meaning_confidence / *_source)

Vi sao can: bo tu nen (data/vocab_seed_core.json) lay nghia tu mot ban so hoa tu
dien cu, nen nghia dau tien doi khi la nghia co hoac nghia chuyen nganh —
`service` ra "cay thanh luong tra", `main` ra "cuoc choi ga". Script dung bo tu
da danh dau san muc do tin cay cua tung nghia, nhung truoc migration nay ba
truong do DUNG LAI O FILE JSON: nap vao DB la mat, nen nguoi hoc khong co cach
nao biet nghia nao chua duoc kiem chung.

Ba cot deu nullable vi item do NGUOI DUNG tu nhap (UC-14, import CSV UC-15,
trich PDF UC-87) khong co khai niem nay — nguoi hoc tu viet nghia cua ho thi
khong can he thong chung nhan.

Gia tri meaning_confidence: 'confirmed' (hai nguon doc lap dong y) |
'single-source' (chi mot nguon) | 'needs-review' (nguon chinh khong duoc doi
chung xac nhan) | 'llm' (nghia do mo hinh viet de, chua co nguoi xac nhan).

Revision ID: c9d0e1f2prov
Revises: b8c9d0e1integrity
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2prov"
down_revision = "b8c9d0e1integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("meaning_confidence", sa.String(20), nullable=True))
    op.add_column("items", sa.Column("meaning_source", sa.String(20), nullable=True))
    op.add_column("items", sa.Column("example_source", sa.String(20), nullable=True))
    # Man "ra soat nghia" loc dung hai nhom can xem (needs-review, llm) tren
    # toan bo item cua mot bo -> index mot cot nay du; khong loc theo *_source.
    op.create_index(
        "ix_items_meaning_confidence", "items", ["meaning_confidence"],
        postgresql_where=sa.text("meaning_confidence IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_items_meaning_confidence", table_name="items")
    op.drop_column("items", "example_source")
    op.drop_column("items", "meaning_source")
    op.drop_column("items", "meaning_confidence")
