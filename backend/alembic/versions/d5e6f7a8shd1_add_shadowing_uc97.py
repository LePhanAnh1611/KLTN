"""UC-97 — Shadowing theo phụ đề video YouTube.

Hai bảng MỚI, không đụng bảng nào đang có:
- shadowing_videos: kho video (admin duyệt) + video riêng của người học.
- shadowing_attempts: từng lần nhại lại một câu, đã chấm.

Không tham chiếu items/interactions/knowledge_states: module luyện nói độc lập
với lõi DKT (CLAUDE.md mục 7).
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8shd1"
down_revision = "c4d5e6f7rmv2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shadowing_videos",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("youtube_id", sa.String(length=11), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("channel", sa.String(length=200), nullable=True),
        sa.Column("topic", sa.String(length=100), nullable=True),
        sa.Column("cefr_level", sa.String(length=2), nullable=True),
        sa.Column("words_per_minute", sa.Float(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("caption_kind", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("vocab_profile", sa.JSON(), nullable=True),
        sa.Column("license", sa.String(length=30), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for col in ("youtube_id", "topic", "cefr_level", "source", "owner_id", "status"):
        op.create_index(f"ix_shadowing_videos_{col}", "shadowing_videos", [col])

    op.create_table(
        "shadowing_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("video_id", sa.BigInteger(), sa.ForeignKey("shadowing_videos.id"),
                  nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("target_text", sa.Text(), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=False),
        sa.Column("clarity", sa.Float(), nullable=False),
        sa.Column("speed_ratio", sa.Float(), nullable=True),
        sa.Column("overall_level", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_shadowing_attempts_user_id", "shadowing_attempts", ["user_id"])
    op.create_index("ix_shadowing_attempts_video_id", "shadowing_attempts", ["video_id"])


def downgrade():
    op.drop_index("ix_shadowing_attempts_video_id", table_name="shadowing_attempts")
    op.drop_index("ix_shadowing_attempts_user_id", table_name="shadowing_attempts")
    op.drop_table("shadowing_attempts")
    for col in ("status", "owner_id", "source", "cefr_level", "topic", "youtube_id"):
        op.drop_index(f"ix_shadowing_videos_{col}", table_name="shadowing_videos")
    op.drop_table("shadowing_videos")
