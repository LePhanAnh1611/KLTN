"""UC-40 — Tiến độ & biểu đồ mastery.

Tổng hợp chỉ số học tập + phân bố mastery (4 dải) + từ điểm yếu (mastery thấp).
Không dùng chuỗi thời gian (chưa lưu lịch sử mastery) — biểu đồ là phân bố hiện tại.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction, counted_interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.progress import (
    MasteryBand,
    MasteryHistory,
    MasteryPoint,
    ProgressResponse,
    WeakItem,
)
from app.services.gamification_service import (
    compute_level,
    default_daily_xp_goal,
    level_title,
    today_xp,
)
from app.services.mastery_service import mastered_threshold, mastered_item_ids
from app.services.review_service import weak_threshold
from app.services import word_set_service

# dải mastery (cận dưới, nhãn) — tăng dần
BANDS = [(0.0, "Mới"), (0.3, "Đang học"), (0.6, "Khá"), (0.9, "Đã thuộc")]
# Ngưỡng "điểm yếu" lấy từ cấu hình (UC-81) để trang Tiến độ và phiên ôn điểm
# yếu (UC-86) luôn nói về cùng một tập từ.
WEAK_LIMIT = 10


def _band_label(mastery: float) -> str:
    label = BANDS[0][1]
    for low, lbl in BANDS:
        if mastery >= low:
            label = lbl
    return label


def get_progress(db: Session, user: User) -> ProgressResponse:
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one_or_none()
    xp = progress.xp if progress else 0
    streak = progress.streak_count if progress else 0
    level, into, forlvl = compute_level(xp)

    settings = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    goal = (settings.daily_xp_goal if settings and settings.daily_xp_goal else None) or default_daily_xp_goal()
    xp_today = today_xp(db, user)

    total_items = db.execute(
        select(func.count())
        .select_from(Item)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(Item.deleted_at.is_(None), WordSet.deleted_at.is_(None), WordSet.owner_id == user.id)
    ).scalar_one()

    # knowledge state của user trên item còn sống thuộc bộ sở hữu
    ks_rows = db.execute(
        select(KnowledgeState.mastery, Item.word, Item.meaning, Item.id, WordSet.name)
        .join(Item, Item.id == KnowledgeState.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            KnowledgeState.user_id == user.id,
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
            WordSet.owner_id == user.id,
        )
    ).all()

    learned = len(ks_rows)
    mastered_ids = mastered_item_ids(db, user.id)
    mastered = len(mastered_ids)

    counts = {lbl: 0 for _, lbl in BANDS}
    for r in ks_rows:
        label = "Đã thuộc" if r.id in mastered_ids else _band_label(r.mastery)
        if label == "Đã thuộc" and r.id not in mastered_ids:
            label = "Khá"
        counts[label] += 1
    distribution = [MasteryBand(label=lbl, count=counts[lbl]) for _, lbl in BANDS]

    weak_max = weak_threshold()
    weak = sorted((r for r in ks_rows if r.mastery < weak_max), key=lambda r: r.mastery)[:WEAK_LIMIT]
    weak_items = [
        WeakItem(item_id=r.id, word=r.word, meaning=r.meaning,
                 word_set_name=r.name, mastery=round(r.mastery, 4))
        for r in weak
    ]

    return ProgressResponse(
        level=level, level_title=level_title(level), xp=xp,
        xp_into_level=into, xp_for_next_level=forlvl, streak_count=streak,
        today_xp=xp_today, daily_xp_goal=goal, daily_goal_reached=xp_today >= goal,
        total_items=total_items, learned_items=learned, mastered_items=mastered,
        mastery_distribution=distribution, weak_items=weak_items,
    )


def mastery_history(db: Session, user: User, item_id: int) -> MasteryHistory:
    """UC-92 — đường cong học tập của một từ.

    Dựng lại từ INTERACTION chứ KHÔNG cần bảng lịch sử riêng: cột
    `predicted_mastery` (thêm cho UC-70) đã ghi sẵn dự đoán của mô hình ngay
    trước từng lượt trả lời. Đây là con số ĐÚNG để vẽ đường cong — nó là dự đoán
    trước khi thấy kết quả, không phải hậu nghiệm.

    Lượt chưa có dự đoán trả `mastery = None` chứ không nội suy: vẽ liền một
    đường qua chỗ không có dữ liệu là bịa ra một đoạn không tồn tại.
    """
    item = word_set_service.get_owned_item(db, user, item_id)

    rows = db.execute(
        select(
            Interaction.answered_at, Interaction.predicted_mastery,
            Interaction.is_correct, Interaction.prediction_source,
            Interaction.exercise_format,
        )
        .where(Interaction.user_id == user.id, Interaction.item_id == item_id, counted_interaction())
        .order_by(Interaction.answered_at.asc())
    ).all()

    points = [
        MasteryPoint(
            answered_at=answered_at,
            mastery=None if mastery is None else float(mastery),
            is_correct=bool(correct),
            source=source,
            exercise_format=fmt,
        )
        for answered_at, mastery, correct, source, fmt in rows
    ]

    current = db.execute(
        select(KnowledgeState.mastery).where(
            KnowledgeState.user_id == user.id, KnowledgeState.item_id == item_id
        )
    ).scalar_one_or_none()

    return MasteryHistory(
        item_id=item.id,
        word=item.word,
        meaning=item.meaning,
        current_mastery=None if current is None else float(current),
        mastered_threshold=mastered_threshold(),
        total_answers=len(points),
        answers_without_prediction=sum(1 for p in points if p.mastery is None),
        points=points,
    )
