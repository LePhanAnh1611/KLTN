"""UC-39 — hoi thoai roleplay voi nhan vat AI

Hai bang: mot phien hoi thoai va cac luot trong phien. Luu tung luot chu khong
gop mot khoi JSON vi con phai doc lai theo thu tu, dem so luot, va hien lich su
— gop khoi thi moi lan them mot cau la ghi lai ca doan.

Module luyen noi DOC LAP voi loi DKT (CLAUDE.md muc 7): bang nay KHONG lien quan
gi toi KNOWLEDGE_STATE hay INTERACTION, va khong duoc dung de suy mastery.

Revision ID: a7b8c9d0uc39
Revises: f6a7b8c9uc94
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0uc39"
down_revision = "f6a7b8c9uc94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"),
                  nullable=False, index=True),
        sa.Column("scenario", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("conversation_id", sa.BigInteger(),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(10), nullable=False),   # 'ai' | 'user'
        sa.Column("text", sa.Text(), nullable=False),
        # Goi y sua cau cua nguoi hoc — NULL khi khong co gi dang sua, khac han
        # voi chuoi rong (da sua nhung khong noi gi).
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("asr_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "ordinal", name="uq_turn_ordinal"),
    )


def downgrade() -> None:
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
