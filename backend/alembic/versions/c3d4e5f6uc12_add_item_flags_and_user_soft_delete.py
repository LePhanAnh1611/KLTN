"""add item_flags (UC-32) + users.deleted_at (UC-12 xóa tài khoản)

Revision ID: c3d4e5f6uc12
Revises: b2c3d4e5uc35
Create Date: 2026-08-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6uc12'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5uc35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'item_flags',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('item_id', sa.BigInteger(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'item_id', name='uq_item_flag_user_item'),
    )
    op.create_index(op.f('ix_item_flags_user_id'), 'item_flags', ['user_id'], unique=False)
    op.create_index(op.f('ix_item_flags_item_id'), 'item_flags', ['item_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_item_flags_item_id'), table_name='item_flags')
    op.drop_index(op.f('ix_item_flags_user_id'), table_name='item_flags')
    op.drop_table('item_flags')
    op.drop_column('users', 'deleted_at')
