"""add role_permissions (UC-74)

Revision ID: c9e0f1a2m7s8
Revises: b8d9e0f1m7s7
Create Date: 2026-07-30

Seed ma trận mặc định: admin có mọi quyền, content lo nội dung & kiểm duyệt,
learner không có quyền quản trị nào.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e0f1a2m7s8'
down_revision: Union[str, Sequence[str], None] = 'b8d9e0f1m7s7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ALL_PERMISSIONS = [
    "admin.overview", "admin.users", "admin.roles", "admin.word_sets", "admin.content",
    "admin.moderation", "admin.reports", "admin.emails", "admin.config",
    "admin.audit", "admin.jobs",
]
CONTENT_PERMISSIONS = [
    "admin.overview", "admin.word_sets", "admin.content", "admin.moderation", "admin.reports",
]


def upgrade() -> None:
    """Upgrade schema."""
    role_permissions = op.create_table(
        'role_permissions',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('permission', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role', 'permission', name='uq_role_permission'),
    )
    op.create_index(op.f('ix_role_permissions_role'), 'role_permissions', ['role'], unique=False)

    op.bulk_insert(role_permissions, [
        {"role": "admin", "permission": key} for key in ALL_PERMISSIONS
    ] + [
        {"role": "content", "permission": key} for key in CONTENT_PERMISSIONS
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_role_permissions_role'), table_name='role_permissions')
    op.drop_table('role_permissions')
