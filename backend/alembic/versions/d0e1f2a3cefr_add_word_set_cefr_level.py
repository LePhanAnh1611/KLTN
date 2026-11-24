"""Muc CEFR cua BO TU (word_sets.cefr_level)

Vi sao can: bo tu nen duoc chia theo (nguon x muc CEFR x tan suat) va buoc dung
du lieu DA tinh ra muc CEFR cua tung bo, nhung luc seed chi con `difficulty`
(beginner/intermediate/advanced) — ba nhom gop mat A1/A2 vao lam mot. Ban do lo
trinh can gom 77 bo thanh 7 cum theo dung muc CEFR, va khong co cot nay thi
frontend phai DOAN muc bang cach doc ten bo ("A1 · Tu 1-50"), tuc la nhet logic
nghiep vu vao React — dung thu CLAUDE.md muc 7 cam.

Nullable: bo do nguoi hoc tu tao (UC-13) khong bat buoc khai muc.

Revision ID: d0e1f2a3cefr
Revises: c9d0e1f2prov
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3cefr"
down_revision = "c9d0e1f2prov"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("word_sets", sa.Column("cefr_level", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("word_sets", "cefr_level")
