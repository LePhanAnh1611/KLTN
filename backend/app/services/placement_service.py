"""UC-11 — Kiểm tra trình độ đầu vào (placement test).

Ước lượng trình độ bằng LUẬT rõ ràng, không phải mô hình: đi từ mức thấp lên,
mức nào đạt tỉ lệ đúng ≥ `placement_pass_ratio` (UC-81) thì công nhận; trình độ
đầu vào là mức cao nhất được công nhận liên tiếp. Kết quả ghi vào
`user_settings.entry_cefr_level` để UC-84 dùng làm điểm xuất phát (BR-RM-02).

Lưu ý phạm vi: hàm này KHÔNG đụng tới cold-start prior của UC-69 (mastery_service)
— logic học/mastery hiện có giữ nguyên.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.placement import CEFR_LEVELS, PlacementAttempt, PlacementQuestion
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.placement import (
    PlacementBankStats,
    PlacementLevelBreakdown,
    PlacementQuestionCreate,
    PlacementQuestionOut,
    PlacementQuestionUpdate,
    PlacementResult,
    PlacementStatus,
    PlacementSubmit,
)
from app.services import config_service

DEFAULT_LEVEL = "A1"          # BR-10: thiếu dữ liệu -> mức thấp nhất
QUESTIONS_PER_LEVEL = 3


def _levels_in_bank(db: Session) -> list[str]:
    rows = db.execute(
        select(PlacementQuestion.cefr_level)
        .where(PlacementQuestion.is_active.is_(True))
        .distinct()
    ).scalars().all()
    return [lv for lv in CEFR_LEVELS if lv in set(rows)]


def get_questions(db: Session, *, rng: random.Random | None = None) -> list[PlacementQuestionOut]:
    """Bước 1 UC-11 — chọn tập câu hỏi TRẢI ĐỀU các mức CEFR, đi từ dễ lên khó."""
    rng = rng or random.Random()
    questions: list[PlacementQuestionOut] = []

    for level in _levels_in_bank(db):
        pool = db.execute(
            select(PlacementQuestion).where(
                PlacementQuestion.is_active.is_(True),
                PlacementQuestion.cefr_level == level,
            )
        ).scalars().all()
        rng.shuffle(pool)
        for q in pool[:QUESTIONS_PER_LEVEL]:
            options = [q.correct_meaning, *q.distractors]
            rng.shuffle(options)
            questions.append(PlacementQuestionOut(
                id=q.id, cefr_level=q.cefr_level, word=q.word, options=options,
            ))
    return questions


def _settings(db: Session, user: User) -> UserSettings:
    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)
        db.flush()
    return settings_row


def estimate_level(per_level: dict[str, dict[str, int]]) -> str:
    """Mức cao nhất mà người học vượt qua LIÊN TIẾP từ dưới lên.

    Dừng ở mức đầu tiên không đạt — tránh trường hợp đoán trúng vài câu ở mức cao
    lại đẩy trình độ lên quá tay.
    """
    pass_ratio = config_service.get_float("placement_pass_ratio")
    achieved = DEFAULT_LEVEL

    for level in CEFR_LEVELS:
        stats = per_level.get(level)
        if not stats or not stats.get("answered"):
            break
        if stats["correct"] / stats["answered"] < pass_ratio:
            break
        achieved = level
    return achieved


def submit(db: Session, user: User, data: PlacementSubmit) -> PlacementResult:
    """Bước 3–5 UC-11 — chấm bài, ước lượng trình độ, ghi nhận điểm xuất phát.

    E1: nộp thiếu câu (thoát giữa chừng) vẫn chấm phần đã làm; không câu nào đúng
    dữ liệu thì về mức mặc định (BR-10).
    """
    answers = {a.question_id: a.answer for a in data.answers}
    per_level: dict[str, dict[str, int]] = {}
    correct_count = 0

    if answers:
        rows = db.execute(
            select(PlacementQuestion).where(PlacementQuestion.id.in_(answers.keys()))
        ).scalars().all()
        for q in rows:
            bucket = per_level.setdefault(q.cefr_level, {"answered": 0, "correct": 0})
            bucket["answered"] += 1
            if answers[q.id] == q.correct_meaning:
                bucket["correct"] += 1
                correct_count += 1

    estimated = estimate_level(per_level)
    return _record(
        db, user, estimated_level=estimated, per_level=per_level,
        answered_count=sum(b["answered"] for b in per_level.values()),
        correct_count=correct_count, status_value="completed",
    )


def skip(db: Session, user: User) -> PlacementResult:
    """Luồng thay thế 1a — "Tôi mới bắt đầu": bỏ test, nhận mức thấp nhất."""
    return _record(
        db, user, estimated_level=DEFAULT_LEVEL, per_level={},
        answered_count=0, correct_count=0, status_value="skipped",
    )


def _record(
    db: Session,
    user: User,
    *,
    estimated_level: str,
    per_level: dict[str, dict[str, int]],
    answered_count: int,
    correct_count: int,
    status_value: str,
) -> PlacementResult:
    attempt = PlacementAttempt(
        user_id=user.id, status=status_value,
        answered_count=answered_count, correct_count=correct_count,
        per_level=per_level, estimated_level=estimated_level,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(attempt)

    settings_row = _settings(db, user)
    settings_row.entry_cefr_level = estimated_level
    db.commit()

    return PlacementResult(
        estimated_level=estimated_level,
        entry_cefr_level=estimated_level,
        answered_count=answered_count,
        correct_count=correct_count,
        per_level=[
            PlacementLevelBreakdown(cefr_level=lv, answered=b["answered"], correct=b["correct"])
            for lv, b in sorted(per_level.items(), key=lambda kv: CEFR_LEVELS.index(kv[0]))
        ],
        skipped=status_value == "skipped",
    )


def get_status(db: Session, user: User) -> PlacementStatus:
    attempt = db.execute(
        select(PlacementAttempt)
        .where(PlacementAttempt.user_id == user.id)
        .order_by(PlacementAttempt.created_at.desc(), PlacementAttempt.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    question_count = db.execute(
        select(func.count()).select_from(PlacementQuestion)
        .where(PlacementQuestion.is_active.is_(True))
    ).scalar_one()

    return PlacementStatus(
        has_placement=attempt is not None,
        entry_cefr_level=settings_row.entry_cefr_level if settings_row else None,
        completed_at=attempt.completed_at if attempt else None,
        question_count=question_count,
    )


def entry_level(db: Session, user: User) -> str:
    """Điểm xuất phát dùng cho UC-84 — chưa làm placement thì mặc định A1
    (bước 3 mục 5 của UC-84)."""
    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    if settings_row is None or not settings_row.entry_cefr_level:
        return DEFAULT_LEVEL
    return settings_row.entry_cefr_level


def require_questions(db: Session) -> None:
    if not _levels_in_bank(db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có câu hỏi kiểm tra đầu vào",
        )


# ---- UC-11 quản trị ngân hàng câu hỏi (Admin, quyền admin.content) ----


def list_questions(
    db: Session, *, cefr_level: str | None = None, only_active: bool = False
) -> list[PlacementQuestion]:
    """Toàn bộ ngân hàng câu hỏi, kể cả câu đang tắt (khác luồng làm bài)."""
    query = select(PlacementQuestion)
    if cefr_level:
        query = query.where(PlacementQuestion.cefr_level == cefr_level)
    if only_active:
        query = query.where(PlacementQuestion.is_active.is_(True))
    return list(db.execute(
        query.order_by(PlacementQuestion.cefr_level, PlacementQuestion.id)
    ).scalars().all())


def bank_stats(db: Session) -> list[PlacementBankStats]:
    """Số câu theo từng mức CEFR.

    Trả đủ 6 mức kể cả mức chưa có câu nào: chỗ trống chính là thứ Admin cần
    thấy — mức không có câu thì bài kiểm tra bỏ qua mức đó và kết quả ước lượng
    kém tin cậy đi.
    """
    rows = db.execute(
        select(
            PlacementQuestion.cefr_level,
            func.count(),
            func.count().filter(PlacementQuestion.is_active.is_(True)),
        ).group_by(PlacementQuestion.cefr_level)
    ).all()
    by_level = {level: (total, active) for level, total, active in rows}

    return [
        PlacementBankStats(
            cefr_level=level,
            total_count=by_level.get(level, (0, 0))[0],
            active_count=by_level.get(level, (0, 0))[1],
        )
        for level in CEFR_LEVELS
    ]


def _get_question(db: Session, question_id: int) -> PlacementQuestion:
    question = db.get(PlacementQuestion, question_id)
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy câu hỏi"
        )
    return question


def _reject_duplicate_meaning(correct: str, distractors: list[str]) -> None:
    """E1 — nhiễu trùng đáp án đúng (hoặc trùng nhau) sẽ tạo câu có 2 đáp án đúng."""
    options = [correct.strip().lower(), *(d.strip().lower() for d in distractors)]
    if len(set(options)) != len(options):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Các lựa chọn phải khác nhau (nhiễu không được trùng đáp án đúng)",
        )


def create_question(db: Session, data: PlacementQuestionCreate) -> PlacementQuestion:
    _reject_duplicate_meaning(data.correct_meaning, data.distractors)
    question = PlacementQuestion(**data.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def update_question(
    db: Session, question_id: int, data: PlacementQuestionUpdate
) -> PlacementQuestion:
    question = _get_question(db, question_id)
    changes = data.model_dump(exclude_unset=True)

    _reject_duplicate_meaning(
        changes.get("correct_meaning", question.correct_meaning),
        changes.get("distractors", question.distractors),
    )
    for field, value in changes.items():
        setattr(question, field, value)

    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: int) -> None:
    """Xóa hẳn.

    Khác Q6 (xóa mềm nội dung người học): PLACEMENT_ATTEMPT chỉ lưu số câu đúng
    theo mức chứ không tham chiếu tới từng câu hỏi, nên xóa không phá vỡ lịch sử.
    Muốn giữ câu mà không cho ra đề thì tắt `is_active`.
    """
    db.delete(_get_question(db, question_id))
    db.commit()
