"""UC-85 — Nâng cấp trình độ CEFR theo mức nắm vững.

Trước UC-85, `user_settings.entry_cefr_level` được gán một lần ở bài kiểm tra đầu
vào (UC-11) rồi đóng băng: người học cày hết A1 vẫn neo ở A1, lộ trình (UC-84)
không bao giờ mở sang mức trên. Đây là chỗ khép vòng đó.

KHÔNG có công thức AI mới. Toàn bộ căn cứ lấy lại từ engine sẵn có:
- trạng thái chặng  <- roadmap_service.get_roadmap (BR-RM-01, dùng lại M_high)
- mastery từng từ   <- KNOWLEDGE_STATE (UC-64)
- mức hiện tại      <- placement_service.entry_level (UC-11)

Quy tắc nghiệp vụ:
- BR-LU-01: mọi chặng thuộc mức hiện tại phải ở trạng thái `mastered`/`achieved`.
- BR-LU-02: mastery trung bình trên các từ của mức hiện tại >= ngưỡng cấu hình,
  và số từ đã có mastery >= số tối thiểu (tránh nâng mức chỉ vì học đúng 3 từ).
- BR-LU-03: đã ở C2 thì không còn mức để nâng.
- BR-LU-04: người học TỪ CHỐI cặp (mức cũ -> mức mới) nào thì không đề xuất lại
  cặp đó nữa. Họ vẫn nâng tay được ở Cài đặt (UC-10).
- BR-LU-05: tại một thời điểm chỉ tồn tại MỘT đề xuất `pending`.

Quyết định là của người học, không phải của hệ thống: chấp nhận thì lộ trình sinh
lại từ mức mới, từ chối thì giữ nguyên mọi thứ.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.learning_stage import LearningStage
from app.models.level_up import LevelUpSuggestion
from app.models.placement import CEFR_LEVELS
from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.level_up import LevelUpStatus, LevelUpSuggestionOut
from app.services import config_service, notification_service, placement_service, roadmap_service

# Trạng thái chặng được tính là "đã qua" ở BR-LU-01. `achieved` là chặng dưới
# trình độ đầu vào mà người học chưa động tới (BR-RM-02) — vẫn coi như đã qua.
_PASSED_STATES = {"mastered", "achieved"}


def required_avg_mastery() -> float:
    return config_service.get_float("level_up_mastery_threshold")


def required_items() -> int:
    return config_service.get_int("level_up_min_items")


def next_level(level: str) -> str | None:
    """BR-LU-03 — mức CEFR kế tiếp, None nếu đã ở mức cao nhất."""
    if level not in CEFR_LEVELS:
        return None
    index = CEFR_LEVELS.index(level)
    return CEFR_LEVELS[index + 1] if index + 1 < len(CEFR_LEVELS) else None


def _pending(db: Session, user: User) -> LevelUpSuggestion | None:
    return db.execute(
        select(LevelUpSuggestion)
        .where(LevelUpSuggestion.user_id == user.id, LevelUpSuggestion.status == "pending")
        .order_by(LevelUpSuggestion.id.desc())
    ).scalars().first()


def _declined(db: Session, user: User, from_level: str, to_level: str) -> bool:
    """BR-LU-04 — đã từ chối đúng cặp mức này chưa."""
    return db.execute(
        select(LevelUpSuggestion.id).where(
            LevelUpSuggestion.user_id == user.id,
            LevelUpSuggestion.status == "declined",
            LevelUpSuggestion.from_level == from_level,
            LevelUpSuggestion.to_level == to_level,
        )
    ).first() is not None


def _mastery_of_level(db: Session, user: User, level: str) -> tuple[float, int]:
    """(mastery trung bình, số từ đã có mastery) trên các chặng thuộc `level`.

    Q2: mastery gắn theo item BẢN SAO trong thư viện người học, nên phải đi từ
    chặng -> bộ gốc -> bản sao (`origin_set_id`) mới đọc đúng số liệu.
    """
    origin_ids = list(db.execute(
        select(LearningStage.word_set_id).where(
            LearningStage.is_active.is_(True), LearningStage.cefr_level == level,
            # Chỉ chặng trên lộ trình của chính người này (v1 / v2)
            LearningStage.roadmap_version == user.roadmap_version,
        )
    ).scalars().all())
    if not origin_ids:
        return 0.0, 0

    copy_ids = list(db.execute(
        select(WordSet.id).where(
            WordSet.owner_id == user.id,
            WordSet.origin_set_id.in_(origin_ids),
            WordSet.deleted_at.is_(None),
        )
    ).scalars().all())
    if not copy_ids:
        return 0.0, 0

    masteries = list(db.execute(
        select(KnowledgeState.mastery)
        .join(Item, Item.id == KnowledgeState.item_id)
        .where(
            KnowledgeState.user_id == user.id,
            Item.word_set_id.in_(copy_ids),
            Item.deleted_at.is_(None),
        )
    ).scalars().all())
    if not masteries:
        return 0.0, 0

    return sum(float(m) for m in masteries) / len(masteries), len(masteries)


def get_status(db: Session, user: User) -> LevelUpStatus:
    """Bảng điều kiện nâng trình độ + đề xuất đang chờ (nếu có).

    Đây cũng là chỗ đánh giá lười: gọi endpoint này mà đủ điều kiện thì đề xuất
    được tạo ngay, không phải chờ hoàn thành thêm một phiên học nữa.
    """
    current = placement_service.entry_level(db, user)
    nxt = next_level(current)

    roadmap = roadmap_service.get_roadmap(db, user)
    at_level = [s for s in roadmap.stages if s.cefr_level == current]
    passed = [s for s in at_level if s.state in _PASSED_STATES]

    avg_mastery, items = _mastery_of_level(db, user, current)

    eligible = (
        nxt is not None
        and len(at_level) > 0                                   # BR-LU-01
        and len(passed) == len(at_level)
        and items >= required_items()                           # BR-LU-02
        and avg_mastery >= required_avg_mastery()
    )

    suggestion = _pending(db, user)
    if suggestion is None and eligible and nxt is not None and not _declined(db, user, current, nxt):
        suggestion = _create(db, user, current, nxt, avg_mastery, items)

    return LevelUpStatus(
        current_level=current,
        next_level=nxt,
        eligible=eligible,
        stages_total=len(at_level),
        stages_mastered=len(passed),
        avg_mastery=round(avg_mastery, 4),
        items_considered=items,
        required_avg_mastery=required_avg_mastery(),
        required_items=required_items(),
        suggestion=LevelUpSuggestionOut.model_validate(suggestion) if suggestion else None,
    )


def _create(
    db: Session, user: User, from_level: str, to_level: str, avg_mastery: float, items: int
) -> LevelUpSuggestion:
    """BR-LU-05 — tạo đề xuất chờ + báo cho người học biết (UC-61)."""
    suggestion = LevelUpSuggestion(
        user_id=user.id, from_level=from_level, to_level=to_level, status="pending",
        avg_mastery=round(avg_mastery, 4), items_considered=items,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)

    notification_service.notify(
        db, user.id, type_="level_up",
        title=f"Bạn đã sẵn sàng lên {to_level}",
        body=(f"Bạn đã nắm vững các chặng mức {from_level} "
              f"(mastery trung bình {avg_mastery:.0%} trên {items} từ). "
              f"Mở lộ trình để chọn nâng lên {to_level} hay giữ mức hiện tại."),
        link="/roadmap",
    )
    return suggestion


def evaluate_after_session(db: Session, user: User) -> LevelUpSuggestion | None:
    """Hook gọi sau khi kết thúc phiên học — best-effort, không được làm hỏng phiên.

    Chạy ở đây (thay vì chỉ lúc mở trang) để đề xuất đến đúng lúc người học vừa
    học xong, kèm thông báo. Lỗi ở bước này chỉ mất một lần đề xuất: lần sau mở
    trang Lộ trình, `get_status` sẽ tạo lại.
    """
    try:
        return get_status(db, user).suggestion
    except Exception:
        db.rollback()
        return None


def _decide(db: Session, user: User, suggestion_id: int, decision: str) -> LevelUpSuggestion:
    suggestion = db.get(LevelUpSuggestion, suggestion_id)
    if suggestion is None or suggestion.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đề xuất")
    if suggestion.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Đề xuất này đã được quyết định"
        )
    suggestion.status = decision
    suggestion.decided_at = datetime.now(timezone.utc)
    return suggestion


def accept(db: Session, user: User, suggestion_id: int) -> LevelUpStatus:
    """Người học đồng ý — nâng `entry_cefr_level`, lộ trình (UC-84) tự sinh lại."""
    suggestion = _decide(db, user, suggestion_id, "accepted")

    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)
    settings_row.entry_cefr_level = suggestion.to_level
    db.commit()

    return get_status(db, user)


def decline(db: Session, user: User, suggestion_id: int) -> LevelUpStatus:
    """Người học từ chối — giữ nguyên mức, và không hỏi lại cặp mức này (BR-LU-04)."""
    _decide(db, user, suggestion_id, "declined")
    db.commit()
    return get_status(db, user)
