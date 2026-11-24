"""UC-94 — bang diem tro choi tu vung

Chi luu DIEM CAO NHAT moi (nguoi, tro choi) chu khong luu tung van: bang xep
hang chi can ky luc, va luu moi van se phinh nhanh hon INTERACTION trong khi
khong ai doc lai.

Ban than cac luot tra loi trong tro choi VAN duoc ghi day du vao INTERACTION qua
luong phien hoc binh thuong (BR-05) — bang nay chi la lop thanh tich, khong phai
nguon du lieu cua DKT.

Revision ID: f6a7b8c9uc94
Revises: e5f6a7b8uc96
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9uc94"
down_revision = "e5f6a7b8uc96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_scores",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("game", sa.String(20), nullable=False),
        sa.Column("best_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plays", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "game", name="uq_game_score_user_game"),
    )
    # Bang xep hang doc theo (tro choi, diem giam dan) -> index ghep dung thu tu do.
    op.create_index("ix_game_scores_game_best", "game_scores", ["game", "best_score"])


def downgrade() -> None:
    op.drop_index("ix_game_scores_game_best", table_name="game_scores")
    op.drop_table("game_scores")
