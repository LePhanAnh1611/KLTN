"""add achievements + categories (UC-79, UC-76)

Revision ID: b8d9e0f1m7s7
Revises: a7c8d9e0m7s4
Create Date: 2026-07-30

Seed 7 huy hiệu vốn định nghĩa cứng trong achievement_service để dữ liệu
USER_ACHIEVEMENTS đã cấp trước đó vẫn khớp code.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d9e0f1m7s7'
down_revision: Union[str, Sequence[str], None] = 'a7c8d9e0m7s4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_ACHIEVEMENTS = [
    ("first_session", "Bước đầu tiên", "Hoàn thành phiên học đầu tiên", "sessions_completed", 1, 1),
    ("xp_100", "Tân binh", "Đạt 100 XP", "xp", 100, 2),
    ("xp_500", "Chăm chỉ", "Đạt 500 XP", "xp", 500, 3),
    ("streak_3", "Kiên trì", "Streak 3 ngày", "streak", 3, 4),
    ("streak_7", "Bền bỉ", "Streak 7 ngày", "streak", 7, 5),
    ("mastered_10", "Vốn từ vững", "Thuộc 10 từ", "mastered", 10, 6),
    ("mastered_50", "Bậc thầy từ vựng", "Thuộc 50 từ", "mastered", 50, 7),
]


def upgrade() -> None:
    """Upgrade schema."""
    achievements = op.create_table(
        'achievements',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('condition_key', sa.String(length=30), nullable=False),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_achievements_code'), 'achievements', ['code'], unique=True)

    op.bulk_insert(achievements, [
        {
            "code": code, "name": name, "description": description,
            "condition_key": condition_key, "threshold": threshold,
            "icon": None, "is_active": True, "sort_order": sort_order,
        }
        for code, name, description, condition_key, threshold, sort_order in SEED_ACHIEVEMENTS
    ])

    op.create_table(
        'categories',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_categories_name'), 'categories', ['name'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_categories_name'), table_name='categories')
    op.drop_table('categories')
    op.drop_index(op.f('ix_achievements_code'), table_name='achievements')
    op.drop_table('achievements')
