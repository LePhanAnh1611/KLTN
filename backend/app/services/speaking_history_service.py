"""Lưu & tra cứu kết quả luyện nói + vòng phản hồi rubric (rubric mục 9).

Tầng này là RANH GIỚI giữa module `app/speaking` (thuần, không biết DB) và phần
còn lại của app. `app/speaking` không import gì ở đây — nhờ vậy module vẫn bê đi
nơi khác được.

Vẫn không đụng tới DKT: không đọc/ghi KNOWLEDGE_STATE, không sinh INTERACTION.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.speaking_attempt import SpeakingAppeal, SpeakingAttempt
from app.models.user import User
from app.schemas.speaking import (
    SpeakingAppealCreate,
    SpeakingAppealRow,
    SpeakingAttemptRow,
    SpeakingHistoryResponse,
    SpeakingProgressPoint,
)
from app.speaking.rubric import CRITERIA
from app.speaking.types import SpeakingAssessment

# Đủ dài để thấy xu hướng, đủ ngắn để không kéo cả nghìn dòng về client
PROGRESS_LIMIT = 30


def save_attempt(
    db: Session,
    user: User,
    assessment: SpeakingAssessment,
    task_prompt: str,
    rubric_version: str,
) -> SpeakingAttempt:
    """Ghi lại một lần chấm. Không lưu file audio (cam kết privacy của module)."""
    metrics = assessment.audio_metrics

    attempt = SpeakingAttempt(
        user_id=user.id,
        task_prompt=task_prompt,
        transcript=assessment.transcript,
        language=str(metrics.get("language", "en")),
        overall_level=assessment.overall_level,
        scores={
            key: {
                "level": score.level,
                "label": score.label,
                "evidence": score.evidence,
                "suggestion": score.suggestion,
                "scored_by": score.scored_by,
                "reason": score.reason,
            }
            for key, score in assessment.scores.items()
        },
        audio_metrics=metrics,
        developmental_feedback=assessment.developmental_feedback,
        warnings=assessment.warnings,
        rubric_version=rubric_version,
        words_per_minute=float(metrics.get("words_per_minute", 0.0)),
        asr_avg_confidence=float(metrics.get("asr_avg_confidence", 0.0)),
        duration_sec=float(metrics.get("duration_sec", 0.0)),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def _to_row(attempt: SpeakingAttempt, appealed: bool) -> SpeakingAttemptRow:
    return SpeakingAttemptRow(
        id=attempt.id,
        task_prompt=attempt.task_prompt,
        transcript=attempt.transcript,
        overall_level=attempt.overall_level,
        scores=attempt.scores,
        audio_metrics=attempt.audio_metrics,
        developmental_feedback=attempt.developmental_feedback,
        warnings=attempt.warnings or [],
        rubric_version=attempt.rubric_version,
        created_at=attempt.created_at,
        has_appeal=appealed,
    )


def _appealed_ids(db: Session, user: User, attempt_ids: list[int]) -> set[int]:
    if not attempt_ids:
        return set()
    return set(db.execute(
        select(SpeakingAppeal.attempt_id).where(
            SpeakingAppeal.user_id == user.id,
            SpeakingAppeal.attempt_id.in_(attempt_ids),
        )
    ).scalars().all())


def get_attempt(db: Session, user: User, attempt_id: int) -> SpeakingAttemptRow:
    attempt = db.get(SpeakingAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài nói"
        )
    return _to_row(attempt, bool(_appealed_ids(db, user, [attempt.id])))


def list_history(
    db: Session, user: User, *, page: int = 1, page_size: int = 10,
) -> SpeakingHistoryResponse:
    """Lịch sử luyện nói + đường tiến bộ.

    `progress` chỉ gồm các lần chấm CÙNG phiên bản rubric mới nhất của người này:
    sau khi calibrate, mức cũ và mức mới không so sánh trực tiếp được (rubric mục
    8), nối chúng vào một đường sẽ vẽ ra xu hướng không có thật.
    """
    base = select(SpeakingAttempt).where(SpeakingAttempt.user_id == user.id)

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    rows = db.execute(
        base.order_by(SpeakingAttempt.created_at.desc(), SpeakingAttempt.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    appealed = _appealed_ids(db, user, [a.id for a in rows])

    latest_version = db.execute(
        select(SpeakingAttempt.rubric_version)
        .where(SpeakingAttempt.user_id == user.id)
        .order_by(SpeakingAttempt.created_at.desc(), SpeakingAttempt.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    progress: list[SpeakingProgressPoint] = []
    if latest_version:
        points = db.execute(
            select(SpeakingAttempt)
            .where(
                SpeakingAttempt.user_id == user.id,
                SpeakingAttempt.rubric_version == latest_version,
            )
            .order_by(SpeakingAttempt.created_at.desc(), SpeakingAttempt.id.desc())
            .limit(PROGRESS_LIMIT)
        ).scalars().all()

        progress = [
            SpeakingProgressPoint(
                attempt_id=p.id,
                created_at=p.created_at,
                overall_level=p.overall_level,
                levels={
                    key: int((p.scores.get(key) or {}).get("level") or 0)
                    for key in CRITERIA
                },
                words_per_minute=p.words_per_minute,
            )
            for p in reversed(points)          # cũ -> mới để vẽ biểu đồ
        ]

    return SpeakingHistoryResponse(
        items=[_to_row(a, a.id in appealed) for a in rows],
        total=total, page=page, page_size=page_size,
        progress=progress,
        progress_rubric_version=latest_version or "",
    )


def create_appeal(
    db: Session, user: User, attempt_id: int, data: SpeakingAppealCreate,
) -> SpeakingAppealRow:
    """Rubric mục 9 — người học báo kết quả chấm chưa đúng.

    KHÔNG tự sửa điểm: đây là dữ liệu để người làm rubric xem lại descriptor.
    Sửa điểm tự động theo lời người học thì rubric mất hết ý nghĩa.

    E1: bài không phải của mình -> 404. E2: đã khiếu nại tiêu chí đó rồi -> 409.
    """
    attempt = db.get(SpeakingAttempt, attempt_id)
    if attempt is None or attempt.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài nói"
        )

    existing = db.execute(
        select(SpeakingAppeal).where(
            SpeakingAppeal.attempt_id == attempt_id,
            SpeakingAppeal.user_id == user.id,
            SpeakingAppeal.criterion == data.criterion,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã gửi phản hồi cho tiêu chí này rồi",
        )

    appeal = SpeakingAppeal(
        attempt_id=attempt_id, user_id=user.id, criterion=data.criterion,
        expected_level=data.expected_level, comment=data.comment.strip(),
    )
    db.add(appeal)
    db.commit()
    db.refresh(appeal)

    scored = (attempt.scores.get(data.criterion) or {}).get("level")
    return SpeakingAppealRow(
        id=appeal.id, attempt_id=attempt_id, criterion=appeal.criterion,
        expected_level=appeal.expected_level, system_level=scored,
        comment=appeal.comment, status=appeal.status, created_at=appeal.created_at,
    )


# ---------------------------------------------------------------- Quản trị


def list_appeals(db: Session, *, only_open: bool = True, limit: int = 100) -> list[dict]:
    """Hàng đợi phản hồi cho người làm rubric.

    Kèm mức hệ thống chấm và transcript: chỗ lệch nhiều giữa `system_level` và
    `expected_level` chính là chỗ descriptor còn mơ hồ (rubric mục 8 bước 4).
    """
    query = (
        select(SpeakingAppeal, SpeakingAttempt, User.display_name)
        .join(SpeakingAttempt, SpeakingAttempt.id == SpeakingAppeal.attempt_id)
        .join(User, User.id == SpeakingAppeal.user_id)
        .order_by(SpeakingAppeal.created_at.desc())
        .limit(limit)
    )
    if only_open:
        query = query.where(SpeakingAppeal.status == "open")

    out: list[dict] = []
    for appeal, attempt, display_name in db.execute(query).all():
        scored = (attempt.scores.get(appeal.criterion) or {}).get("level")
        out.append({
            "id": appeal.id,
            "attempt_id": appeal.attempt_id,
            "user_name": display_name,
            "criterion": appeal.criterion,
            "system_level": scored,
            "expected_level": appeal.expected_level,
            "gap": (
                abs(appeal.expected_level - scored)
                if appeal.expected_level is not None and scored is not None else None
            ),
            "comment": appeal.comment,
            "transcript": attempt.transcript,
            "task_prompt": attempt.task_prompt,
            "rubric_version": attempt.rubric_version,
            "status": appeal.status,
            "created_at": appeal.created_at,
        })
    return out


def mark_reviewed(db: Session, appeal_id: int) -> None:
    appeal = db.get(SpeakingAppeal, appeal_id)
    if appeal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phản hồi"
        )
    appeal.status = "reviewed"
    appeal.reviewed_at = datetime.now(timezone.utc)
    db.commit()
