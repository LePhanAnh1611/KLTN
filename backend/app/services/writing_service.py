"""UC-37 luyện viết Việt→Anh · UC-38 sổ tay câu.

Đề bài lấy từ chính từ vựng người học đang học: mỗi câu ví dụ của một item vừa
sức (UC-65) trở thành một đề dịch. Nhờ vậy bài viết bám sát vốn từ hiện có thay
vì là một kho câu rời rạc phải quản lý riêng.

Chấm bài đi qua `llm_client`; không có LLM thì rơi về bộ chấm heuristic ở dưới.
Cả hai đường đều ghi rõ `grader` để giao diện nói thật người học đang đọc nhận
xét của ai.
"""
from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.user import User
from app.models.word_set import WordSet
from app.models.writing import SentenceNote, WritingSubmission
from app.schemas.writing import (
    NoteCreate,
    NoteRow,
    NoteUpdate,
    WritingPrompt,
    WritingResult,
    WritingSubmitRequest,
)
from app.services import llm_client
from app.services.word_set_service import get_owned_word_set


def list_prompts(db: Session, user: User, word_set_id: int, limit: int = 5) -> list[WritingPrompt]:
    """Đề dịch lấy từ câu ví dụ của item trong bộ.

    E1: bộ chưa có câu ví dụ nào -> 400 kèm lý do. Giống UC-28 điền khuyết: đây
    là thiếu dữ liệu chứ không phải lỗi hệ thống.
    """
    get_owned_word_set(db, user, word_set_id)

    rows = db.execute(
        select(Item)
        .where(
            Item.word_set_id == word_set_id,
            Item.deleted_at.is_(None),
            Item.example.isnot(None),
            Item.example != "",
        )
        .order_by(func.random())
        .limit(limit)
    ).scalars().all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bộ từ vựng chưa có câu ví dụ nào để tạo đề luyện viết",
        )

    return [
        WritingPrompt(
            item_id=item.id, word=item.word,
            # Đề là NGHĨA tiếng Việt; người học phải tự dựng lại câu tiếng Anh
            prompt_vi=f"Đặt một câu tiếng Anh dùng từ “{item.word}” (nghĩa: {item.meaning}).",
            reference_en=item.example,
        )
        for item in rows
    ]


_WORD_RE = re.compile(r"[A-Za-z']+")


def _heuristic_grade(prompt_vi: str, answer_en: str) -> dict:
    """Bộ chấm dự phòng khi không có LLM.

    Chỉ kiểm được những gì kiểm được một cách chắc chắn: độ dài, có dùng đúng từ
    cần luyện không, viết hoa đầu câu và dấu kết câu. KHÔNG cố đoán ngữ pháp —
    đưa ra nhận xét ngữ pháp sai còn tệ hơn là không nhận xét gì.
    """
    words = _WORD_RE.findall(answer_en)
    issues: list[str] = []
    score = 100.0

    target = re.search(r"“(.+?)”", prompt_vi)
    target_word = target.group(1).lower() if target else None

    if len(words) < 3:
        issues.append("Câu quá ngắn - hãy viết thành câu hoàn chỉnh (tối thiểu 3 từ).")
        score -= 40
    if target_word and target_word not in {w.lower() for w in words}:
        issues.append(f"Chưa dùng từ cần luyện: “{target_word}”.")
        score -= 30
    if answer_en[:1].islower():
        issues.append("Câu nên viết hoa chữ cái đầu.")
        score -= 10
    if not answer_en.rstrip().endswith((".", "!", "?")):
        issues.append("Câu nên kết thúc bằng dấu chấm câu.")
        score -= 10

    return {
        "score": max(0.0, score),
        "feedback": (
            " ".join(issues) if issues
            else "Câu đủ dài, có dùng từ cần luyện và đúng quy ước viết câu."
        ),
        # Không có LLM thì không bịa ra bản dịch mẫu
        "suggestion": None,
    }


def submit(db: Session, user: User, data: WritingSubmitRequest) -> WritingResult:
    """Nộp bài và nhận nhận xét. LLM lỗi/thiếu key -> chấm heuristic, không chặn."""
    graded = llm_client.grade_writing(data.prompt_vi, data.answer_en)
    grader = "llm"
    if graded is None:
        graded = _heuristic_grade(data.prompt_vi, data.answer_en)
        grader = "heuristic"

    submission = WritingSubmission(
        user_id=user.id, prompt_vi=data.prompt_vi, answer_en=data.answer_en,
        score=graded["score"], feedback=graded["feedback"],
        suggestion=graded["suggestion"], grader=grader,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return WritingResult(
        id=submission.id, prompt_vi=submission.prompt_vi, answer_en=submission.answer_en,
        score=submission.score, feedback=submission.feedback,
        suggestion=submission.suggestion, grader=submission.grader,
        created_at=submission.created_at,
    )


def list_submissions(db: Session, user: User, limit: int = 20) -> list[WritingResult]:
    rows = db.execute(
        select(WritingSubmission)
        .where(WritingSubmission.user_id == user.id)
        .order_by(WritingSubmission.created_at.desc(), WritingSubmission.id.desc())
        .limit(limit)
    ).scalars().all()
    return [
        WritingResult(
            id=s.id, prompt_vi=s.prompt_vi, answer_en=s.answer_en, score=s.score,
            feedback=s.feedback, suggestion=s.suggestion, grader=s.grader,
            created_at=s.created_at,
        )
        for s in rows
    ]


# ---------------------------------------------------------------- UC-38


def _get_own_note(db: Session, user: User, note_id: int) -> SentenceNote:
    note = db.get(SentenceNote, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ghi chú"
        )
    return note


def create_note(db: Session, user: User, data: NoteCreate) -> SentenceNote:
    """UC-38 — lưu một câu vào sổ tay.

    `submission_id` nếu có phải là bài của chính người này: không thì người dùng
    có thể trỏ ghi chú của mình sang bài viết của người khác.
    """
    if data.submission_id is not None:
        owned = db.execute(
            select(WritingSubmission.id).where(
                WritingSubmission.id == data.submission_id,
                WritingSubmission.user_id == user.id,
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài viết"
            )

    note = SentenceNote(user_id=user.id, **data.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def update_note(db: Session, user: User, note_id: int, data: NoteUpdate) -> SentenceNote:
    note = _get_own_note(db, user, note_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, user: User, note_id: int) -> None:
    db.delete(_get_own_note(db, user, note_id))
    db.commit()


def list_notes(db: Session, user: User, q: str | None = None) -> list[NoteRow]:
    query = select(SentenceNote).where(SentenceNote.user_id == user.id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            SentenceNote.text_en.ilike(pattern) | SentenceNote.note.ilike(pattern)
        )
    rows = db.execute(
        query.order_by(SentenceNote.created_at.desc(), SentenceNote.id.desc())
    ).scalars().all()
    return [NoteRow.model_validate(n) for n in rows]
