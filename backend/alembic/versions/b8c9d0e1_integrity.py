"""Preserve answer retries and completed session receipts.

Revision ID: b8c9d0e1integrity
Revises: a7b8c9d0uc39
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1integrity"
down_revision = "a7b8c9d0uc39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interactions", sa.Column("client_answer_id", sa.String(36), nullable=True))
    op.add_column("interactions", sa.Column("request_hash", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_interaction_client_answer", "interactions", ["session_id", "client_answer_id"])
    op.add_column("sessions", sa.Column("completion_summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "completion_summary")
    op.drop_constraint("uq_interaction_client_answer", "interactions", type_="unique")
    op.drop_column("interactions", "request_hash")
    op.drop_column("interactions", "client_answer_id")
