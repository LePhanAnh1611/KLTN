"""Pilot — bài kiểm tra cuối: kiểm chứng mastery của DKT bằng một bài độc lập.

Câu hỏi khóa luận phải trả lời: *"mastery hệ thống đưa ra có đúng với thực tế
không, đúng bao nhiêu?"*. Lượt trả lời trong lúc học đã cho một câu trả lời
(dự đoán chốt trước mỗi lượt — UC-70), nhưng các lượt đó do chính hệ thống chọn
và có phản hồi ngay. Bài này bổ sung một phép đo NGOÀI vòng học:

- Từ được lấy **phân tầng theo mastery hiện tại** (5 khoảng đều 0–1), nên mọi
  mức mastery đều có người kiểm — chứ không chỉ các từ hệ thống đang ưu tiên.
- Dạng **gõ từ** (thấy nghĩa, gõ từ tiếng Anh): không có đáp án sẵn để đoán mò
  như trắc nghiệm. Chỉ gợi ý chữ cái đầu + độ dài để khỏi nhầm từ đồng nghĩa.
- Không hiện đáp án từng câu, và phiên là `practice_only` nên KHÔNG xê dịch
  lịch ôn. Mỗi lượt vẫn ghi Interaction đầy đủ (BR-05) kèm dự đoán của DKT
  chốt ngay trước câu đó, `selection_reason='validation'`.
- Mỗi người làm một lần. Admin mở bài bằng cấu hình `validation_open`.

Danh sách từ đã bốc được giữ trong `sessions.completion_summary` khi phiên còn
dở (trường đó chỉ được ghi đè lúc hoàn thành), để thoát ra vào lại vẫn đúng đề.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.session import StudySession
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.validation import ValidationQuestion, ValidationStart, ValidationStatus
from app.services import config_service, recommend_service
from app.services.session_service import VALIDATION_MODE

#: Số khoảng mastery khi lấy mẫu phân tầng: [0, .2), [.2, .4), ..., [.8, 1].
N_BINS = 5
#: Dưới số từ này thì bài kiểm tra không nói lên được điều gì.
MIN_ITEMS = 10


def _bin_of(p: float) -> int:
    return min(int(p * N_BINS), N_BINS - 1)


def _validation_sessions(db: Session, user: User) -> list[StudySession]:
    return list(db.execute(
        select(StudySession).where(
            StudySession.user_id == user.id, StudySession.mode == VALIDATION_MODE,
        ).order_by(StudySession.id)
    ).scalars().all())


def _candidate_items(db: Session, user: User) -> list[Item]:
    """Từ người học ĐÃ từng gặp (có Interaction ngoài bài kiểm tra), còn sống,
    vẫn thuộc thư viện của họ. Từ chưa gặp thì không có gì để kiểm chứng."""
    seen = select(Interaction.item_id).where(
        Interaction.user_id == user.id,
        Interaction.selection_reason.is_distinct_from("validation"),
    ).distinct()
    owned = select(WordSet.id).where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
    return list(db.execute(
        select(Item).where(
            Item.id.in_(seen), Item.deleted_at.is_(None), Item.word_set_id.in_(owned),
            Item.meaning != "",
        )
    ).scalars().all())


def get_status(db: Session, user: User) -> ValidationStatus:
    sessions = _validation_sessions(db, user)
    done = any(s.status == "completed" for s in sessions)
    in_progress = next((s for s in sessions if s.status == "in_progress"), None)
    return ValidationStatus(
        open=config_service.get_bool("validation_open"),
        done=done,
        in_progress_session_id=in_progress.id if in_progress else None,
        eligible_items=len(_candidate_items(db, user)),
        size=config_service.get_int("validation_size"),
        min_items=MIN_ITEMS,
    )


def stratified_sample(
    scored: list[tuple[Item, float]], size: int, rng: random.Random | None = None
) -> list[tuple[Item, float]]:
    """Lấy `size` từ chia đều cho N_BINS khoảng mastery; khoảng nào thiếu thì bù
    ngẫu nhiên từ phần còn lại. Thứ tự kết quả được xáo."""
    rng = rng or random
    bins: list[list[tuple[Item, float]]] = [[] for _ in range(N_BINS)]
    for pair in scored:
        bins[_bin_of(pair[1])].append(pair)

    quota = size // N_BINS
    chosen: list[tuple[Item, float]] = []
    for members in bins:
        rng.shuffle(members)
        chosen.extend(members[:quota])
    taken = {it.id for it, _ in chosen}
    rest = [pair for pair in scored if pair[0].id not in taken]
    rng.shuffle(rest)
    chosen.extend(rest[: max(0, size - len(chosen))])
    rng.shuffle(chosen)
    return chosen


def _questions(db: Session, session: StudySession) -> list[ValidationQuestion]:
    planned: list[int] = (session.completion_summary or {}).get("planned_item_ids", [])
    answered = set(db.execute(
        select(Interaction.item_id).where(Interaction.session_id == session.id)
    ).scalars().all())
    items = {
        it.id: it for it in db.execute(select(Item).where(Item.id.in_(planned))).scalars().all()
    }
    return [
        ValidationQuestion(
            item_id=items[i].id,
            meaning=items[i].meaning,
            part_of_speech=items[i].part_of_speech,
            first_letter=items[i].word[:1],
            length=len(items[i].word),
        )
        for i in planned if i in items and i not in answered
    ]


def start(db: Session, user: User) -> ValidationStart:
    """Bắt đầu (hoặc vào lại) bài kiểm tra cuối."""
    if not config_service.get_bool("validation_open"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Bài kiểm tra cuối chưa mở")
    sessions = _validation_sessions(db, user)
    if any(s.status == "completed" for s in sessions):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Bạn đã làm bài kiểm tra cuối rồi")
    current = next((s for s in sessions if s.status == "in_progress"), None)
    if current is not None:
        return ValidationStart(session_id=current.id, questions=_questions(db, current))

    candidates = _candidate_items(db, user)
    if len(candidates) < MIN_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cần học ít nhất {MIN_ITEMS} từ trước khi làm bài kiểm tra "
                   f"(hiện {len(candidates)})",
        )

    # Mastery HIỆN TẠI của từng từ — cùng phép chấm với gợi ý (UC-65), một lượt DKT.
    scored = recommend_service.score_items(db, user, candidates, None)
    picked = stratified_sample(scored, config_service.get_int("validation_size"))

    session = StudySession(
        user_id=user.id,
        word_set_id=None,
        mode=VALIDATION_MODE,
        practice_only=True,  # không đụng lịch ôn
        status="in_progress",
        started_at=datetime.now(timezone.utc),
        completion_summary={"planned_item_ids": [it.id for it, _ in picked]},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ValidationStart(session_id=session.id, questions=_questions(db, session))
