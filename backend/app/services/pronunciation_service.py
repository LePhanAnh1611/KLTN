"""Lưu & tra cứu kết quả luyện phát âm (mở rộng UC-29).

Điểm do Web Speech API của trình duyệt chấm, phụ thuộc micro và tiếng ồn xung
quanh, nên CỐ Ý không ghi vào INTERACTION và không đụng tới mastery/lịch ôn: đầu
vào của DKT phải là bằng chứng học tập đáng tin. Đây là nhật ký tự đánh giá,
tách bạch hoàn toàn với luồng học.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.pronunciation_attempt import PronunciationAttempt
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.pronunciation import (
    ItemBestScore,
    PronunciationAttemptCreate,
    PronunciationAttemptRow,
    PronunciationStats,
)
from app.services.word_set_service import get_owned_item, get_owned_word_set

RECENT_LIMIT = 20


def record_attempt(
    db: Session, user: User, data: PronunciationAttemptCreate
) -> PronunciationAttempt:
    """Ghi một lần luyện TỪ (trình duyệt chấm). Chỉ nhận từ trong thư viện của mình."""
    get_owned_item(db, user, data.item_id)

    attempt = PronunciationAttempt(
        user_id=user.id, item_id=data.item_id, kind="word",
        score=data.score, transcript=data.transcript,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def get_stats(db: Session, user: User) -> PronunciationStats:
    """Tổng hợp + vài lần thử gần nhất."""
    total, words, average, best = db.execute(
        select(
            func.count(),
            func.count(func.distinct(PronunciationAttempt.item_id)),
            func.coalesce(func.avg(PronunciationAttempt.score), 0.0),
            func.coalesce(func.max(PronunciationAttempt.score), 0.0),
        ).where(PronunciationAttempt.user_id == user.id)
    ).one()

    rows = db.execute(
        select(PronunciationAttempt, Item)
        .join(Item, Item.id == PronunciationAttempt.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            PronunciationAttempt.user_id == user.id,
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
        )
        .order_by(PronunciationAttempt.created_at.desc(), PronunciationAttempt.id.desc())
        .limit(RECENT_LIMIT)
    ).all()

    return PronunciationStats(
        total_attempts=total,
        words_practiced=words,
        average_score=round(float(average), 1),
        best_score=round(float(best), 1),
        recent=[
            PronunciationAttemptRow(
                id=a.id, item_id=item.id, word=item.word, meaning=item.meaning,
                score=a.score, transcript=a.transcript, created_at=a.created_at,
            )
            for a, item in rows
        ],
    )


def best_scores(db: Session, user: User, word_set_id: int) -> list[ItemBestScore]:
    """Điểm cao nhất + số lần thử của từng từ ĐÃ LUYỆN trong một bộ từ.

    Nguồn cho 3 ô thống kê đầu trang Luyện phát âm. Trước đây các ô đó đếm trong
    state của màn hình nên F5/đổi trang là về 0, dù lần thử đã nằm trong DB.
    Tính cả hai chế độ (đọc từ + đọc câu): cùng thang 100, và với người học thì
    đọc câu chứa từ cũng là đã luyện từ đó. Từ đã xóa mềm không tính.
    """
    get_owned_word_set(db, user, word_set_id)
    rows = db.execute(
        select(
            PronunciationAttempt.item_id,
            func.max(PronunciationAttempt.score),
            func.count(),
        )
        .join(Item, Item.id == PronunciationAttempt.item_id)
        .where(
            PronunciationAttempt.user_id == user.id,
            Item.word_set_id == word_set_id,
            Item.deleted_at.is_(None),
        )
        .group_by(PronunciationAttempt.item_id)
    ).all()
    return [
        ItemBestScore(item_id=item_id, best_score=round(float(score), 1), attempts=n)
        for item_id, score, n in rows
    ]


def record_read_aloud(db: Session, user: User, result) -> PronunciationAttempt:
    """Ghi một lần ĐỌC CÂU MẪU (máy chủ chấm bằng Whisper).

    Chốt cả `target_text` vào bản ghi: người dùng sửa được câu ví dụ của item,
    và khi đó kết quả cũ sẽ không còn giải thích được nếu chỉ tham chiếu động.
    """
    attempt = PronunciationAttempt(
        user_id=user.id,
        item_id=result.item_id,
        kind="sentence",
        # Quy về thang 100 cho cùng đơn vị với luyện từ, để một biểu đồ tiến bộ
        # hiển thị được cả hai chế độ.
        score=round(result.accuracy * 100, 1),
        transcript=result.transcript[:300],
        target_text=result.expected_text,
        detail={
            "overall_level": result.overall_level,
            "accuracy": result.accuracy,
            "clarity": result.clarity,
            "missed_words": result.missed_words,
            "extra_words": result.extra_words,
            "words": result.words,
            "aspects": [
                {
                    "key": a.key, "label": a.label, "level": a.level,
                    "level_label": a.level_label, "detail": a.detail,
                    "suggestion": a.suggestion,
                }
                for a in result.aspects
            ],
            "audio_metrics": result.audio_metrics,
            "feedback": result.feedback,
            "warnings": result.warnings,
        },
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def list_attempts(db: Session, user: User, item_id: int, kind: str | None = None):
    """Lịch sử luyện của MỘT từ, mới nhất trước.

    Trang luyện đọc lịch sử qua đây thay vì giữ kết quả trong state của màn hình
    — chuyển tab rồi quay lại vẫn thấy kết quả vừa chấm.
    """
    query = (
        select(PronunciationAttempt, Item)
        .join(Item, Item.id == PronunciationAttempt.item_id)
        .where(
            PronunciationAttempt.user_id == user.id,
            PronunciationAttempt.item_id == item_id,
        )
        .order_by(PronunciationAttempt.created_at.desc(), PronunciationAttempt.id.desc())
        .limit(20)
    )
    if kind:
        query = query.where(PronunciationAttempt.kind == kind)
    return db.execute(query).all()
