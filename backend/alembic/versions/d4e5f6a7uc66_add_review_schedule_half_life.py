"""UC-66 ban sua: lich on nham muc nho muc tieu — them cot half_life

Vi sao can cot moi: luat cu suy interval thang tu mastery (bang bac 1/2/4/7
ngay) nen khong can nho gi giua hai lan on. Luat moi giu mot uoc luong NUA DOI
(so ngay de xac suat nho con mot nua) cho tung cap (nguoi, tu), cap nhat sau moi
luot — giong vai tro cua `ease_factor` voi SM-2, nhung o thang thoi gian that.

Nullable: lich on da co tu truoc chua co uoc luong nao, va dien mot con so bia
vao do se lam lich cua ho nhay lung tung. De NULL thi lan on ke tiep tu khoi tao
tu gia tri mac dinh trong cau hinh.

Revision ID: d4e5f6a7uc66
Revises: c3d4e5f6uc70
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7uc66"
down_revision = "c3d4e5f6uc70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_schedules",
        sa.Column("half_life_days", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_schedules", "half_life_days")
