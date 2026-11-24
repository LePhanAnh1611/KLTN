"""UC-84 — Lộ trình học cá nhân hóa (bản đồ chặng).

Đây là VIEW trực quan hóa engine sẵn có, không phải AI mới:
- mastery item  <- KNOWLEDGE_STATE (UC-64)
- chặng tiếp theo <- chặng chưa hoàn thành đầu tiên từ mức đầu vào
- điểm xuất phát <- placement_service.entry_level (UC-11)

Q1/Q2: tải bộ công khai là SAO CHÉP, mastery gắn theo item BẢN SAO. Nên với mỗi
chặng ta phải tìm bản sao của người học (`origin_set_id`) rồi đọc mastery ở đó;
chưa tải thì chặng coi như chưa có tiến độ.
"""
from __future__ import annotations

import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings
from app.models.interaction import Interaction, counted_interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.placement import CEFR_LEVELS
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.roadmap import RoadmapResponse, RoadmapStage, StageSummary, StageWord
from app.services import config_service, placement_service, review_service


def _level_rank(level: str) -> int:
    return CEFR_LEVELS.index(level) if level in CEFR_LEVELS else 0


def _active_stages(db: Session, user: User) -> list[LearningStage]:
    """Bước 2 mục 5 — chặng đang bật CỦA PHIÊN BẢN LỘ TRÌNH người học
    (`users.roadmap_version`), sắp theo (cefr_level, order_index)."""
    stages = db.execute(
        select(LearningStage).where(
            LearningStage.is_active.is_(True),
            LearningStage.roadmap_version == user.roadmap_version,
        )
    ).scalars().all()
    return sorted(stages, key=lambda s: (_level_rank(s.cefr_level), s.order_index, s.id))


def _user_copies(db: Session, user: User, origin_ids: list[int]) -> dict[int, int]:
    """{id bộ gốc: id bản sao trong thư viện người học} (Q1)."""
    if not origin_ids:
        return {}
    rows = db.execute(
        select(WordSet.origin_set_id, WordSet.id).where(
            WordSet.owner_id == user.id,
            WordSet.origin_set_id.in_(origin_ids),
            WordSet.deleted_at.is_(None),
        )
    ).all()
    return {origin_id: copy_id for origin_id, copy_id in rows}


def _items_of(db: Session, word_set_id: int) -> list[Item]:
    return list(db.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalars().all())


def _mastery_map(db: Session, user: User, item_ids: list[int]) -> dict[int, float]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(KnowledgeState.item_id, KnowledgeState.mastery).where(
            KnowledgeState.user_id == user.id,
            KnowledgeState.item_id.in_(item_ids),
        )
    ).all()
    return {item_id: float(mastery) for item_id, mastery in rows}


def get_roadmap(db: Session, user: User) -> RoadmapResponse:
    """Trả bản đồ chặng kèm trạng thái từng chặng theo BR-RM-01..05."""
    entry = placement_service.entry_level(db, user)
    # UC-10: mục tiêu CEFR trước đây lưu rồi bỏ đó, không chỗ nào đọc. Hiện nó
    # ngay trên bản đồ lộ trình — đó là chỗ duy nhất "mục tiêu" có nghĩa.
    target = db.execute(
        select(UserSettings.target_cefr_level).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    entry_rank = _level_rank(entry)

    stages = _active_stages(db, user)
    if not stages:
        return RoadmapResponse(entry_level=entry, target_level=target, stages=[])   # Ngoại lệ: chưa có chặng

    copies = _user_copies(db, user, [s.word_set_id for s in stages])

    m_high = config_service.get_float("stage_mastery_high")        # BR-RM-01
    mastered_ratio = config_service.get_float("stage_mastered_ratio")

    computed: list[dict] = []
    for stage in stages:
        origin_items = _items_of(db, stage.word_set_id)
        copy_id = copies.get(stage.word_set_id)

        # Mastery gắn theo item BẢN SAO (Q2); chưa tải -> chưa có tiến độ
        progress_items = _items_of(db, copy_id) if copy_id else []
        mastery = _mastery_map(db, user, [it.id for it in progress_items])

        items_total = len(origin_items)
        items_mastered = sum(1 for it in progress_items if mastery.get(it.id, 0.0) >= m_high)
        started = bool(mastery)
        ratio = (items_mastered / items_total) if items_total else 0.0

        computed.append({
            "stage": stage,
            "copy_id": copy_id,
            "items_total": items_total,
            "items_mastered": items_mastered,
            # round() trước ceil để 0.8 * 50 = 40.000000001 không thành 41
            "items_needed": min(items_total, math.ceil(round(mastered_ratio * items_total, 6))),
            "items_learning": max(len(mastery) - items_mastered, 0),
            "progress_pct": round(ratio * 100, 1),
            "is_mastered": items_total > 0 and ratio >= mastered_ratio,   # BR-RM-01
            "started": started,
        })

    # Chỉ gợi ý chặng chưa hoàn thành đầu tiên từ mức đầu vào.
    # DKT vẫn chọn từ vừa sức bên trong phiên học của chặng.
    candidates: list[int] = []
    for index, row in enumerate(computed):
        stage = row["stage"]
        if row["is_mastered"]:
            continue
        # Học bổ sung mức thấp hơn không đổi điểm xuất phát của lộ trình.
        if _level_rank(stage.cefr_level) < entry_rank:
            continue
        candidates.append(index)

    current_index: int | None = candidates[0] if candidates else None

    result: list[RoadmapStage] = []
    for index, row in enumerate(computed):
        stage = row["stage"]

        # Thứ tự ưu tiên theo mục 4: achieved/mastered -> current -> in_progress -> locked
        if row["is_mastered"]:
            state = "mastered"                                   # BR-RM-01
        elif _level_rank(stage.cefr_level) < entry_rank:
            state = "achieved"                                   # BR-RM-02
        elif current_index is not None and index == current_index:
            state = "current"                                    # BR-RM-03
        elif row["started"]:
            state = "in_progress"                                # BR-RM-05
        else:
            state = "locked"                                     # BR-RM-04

        result.append(RoadmapStage(
            id=stage.id, title=stage.title, cefr_level=stage.cefr_level,
            order_index=stage.order_index, word_set_id=stage.word_set_id,
            track=stage.track, topic=stage.topic,
            state=state, progress_pct=row["progress_pct"],
            items_mastered=row["items_mastered"], items_total=row["items_total"],
            items_needed=row["items_needed"], items_learning=row["items_learning"],
            is_recommended=(current_index is not None and index == current_index),
            user_word_set_id=row["copy_id"],
            is_skipped=_level_rank(stage.cefr_level) < entry_rank,
        ))

    return RoadmapResponse(entry_level=entry, target_level=target, stages=result)


TOP_WORDS = 5   # số từ hiển thị ở mỗi cột "điểm mạnh" / "cần ôn lại"


def get_stage_summary(db: Session, user: User, stage_id: int) -> StageSummary:
    """Tổng kết một chặng: nắm được gì, còn yếu gì, đi tiếp đâu.

    Dùng lại nguyên `get_roadmap` để lấy trạng thái/tiến độ, thay vì tính lại
    theo một công thức thứ hai — hai chỗ tính khác nhau là hai chỗ sẽ lệch nhau.
    """
    stage = db.get(LearningStage, stage_id)
    if stage is None or not stage.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chặng"
        )

    roadmap = get_roadmap(db, user)
    row = next((s for s in roadmap.stages if s.id == stage_id), None)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chặng không có trên lộ trình của bạn"
        )

    # Mastery gắn theo item BẢN SAO (Q2); chưa tải bộ thì chưa có gì để tổng kết
    words: list[StageWord] = []
    answers_total = answers_correct = 0
    if row.user_word_set_id:
        items = _items_of(db, row.user_word_set_id)
        item_ids = [it.id for it in items]
        mastery = _mastery_map(db, user, item_ids)

        words = [
            StageWord(
                item_id=it.id, word=it.word, meaning=it.meaning,
                mastery=round(mastery.get(it.id, 0.0), 4),
            )
            for it in items
            if it.id in mastery          # chưa từng học thì chưa xếp mạnh/yếu được
        ]

        if item_ids:
            answers_total, answers_correct = db.execute(
                select(
                    func.count(),
                    func.count().filter(Interaction.is_correct.is_(True)),
                ).where(
                    Interaction.user_id == user.id,
                    Interaction.item_id.in_(item_ids),
                    counted_interaction(),
                )
            ).one()

    ranked = sorted(words, key=lambda w: w.mastery, reverse=True)
    weak_max = review_service.weak_threshold()
    next_id, next_title = _next_stage(roadmap, stage_id)

    return StageSummary(
        stage_id=stage.id, title=stage.title, cefr_level=stage.cefr_level,
        state=row.state, is_complete=row.state in ("mastered", "achieved"),
        items_total=row.items_total, items_mastered=row.items_mastered,
        progress_pct=row.progress_pct,
        answers_total=answers_total, answers_correct=answers_correct,
        accuracy=(answers_correct / answers_total) if answers_total else 0.0,
        strongest=ranked[:TOP_WORDS],
        # Chỉ liệt kê từ thực sự dưới ngưỡng — chặng hoàn hảo thì cột này rỗng,
        # không bịa ra "điểm yếu" chỉ để lấp chỗ trống.
        weakest=[w for w in reversed(ranked) if w.mastery < weak_max][:TOP_WORDS],
        next_stage_id=next_id,
        next_stage_title=next_title,
    )


def _next_stage(roadmap: RoadmapResponse, stage_id: int) -> tuple[int | None, str | None]:
    """Chặng kế tiếp trên bản đồ — ưu tiên chặng đang được gợi ý (BR-RM-03),
    nếu nó chính là chặng vừa xong thì lấy chặng chưa hoàn thành liền sau."""
    recommended = next(
        (s for s in roadmap.stages if s.is_recommended and s.id != stage_id), None
    )
    if recommended:
        return recommended.id, recommended.title

    index = next((i for i, s in enumerate(roadmap.stages) if s.id == stage_id), None)
    if index is None:
        return None, None
    for stage in roadmap.stages[index + 1:]:
        if stage.state not in ("mastered", "achieved"):
            return stage.id, stage.title
    return None, None
