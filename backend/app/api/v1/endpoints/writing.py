"""UC-37 luyện viết · UC-38 sổ tay câu."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.writing import (
    NoteCreate,
    NoteRow,
    NoteUpdate,
    WritingPrompt,
    WritingResult,
    WritingSubmitRequest,
)
from app.services import writing_service

router = APIRouter()


@router.get("/writing/prompts", response_model=list[WritingPrompt])
def prompts(
    word_set_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WritingPrompt]:
    """UC-37 — đề dịch sinh từ từ vựng trong bộ (E1: chưa có câu ví dụ -> 400)."""
    return writing_service.list_prompts(db, current_user, word_set_id, limit)


@router.post("/writing/submissions", response_model=WritingResult,
             status_code=status.HTTP_201_CREATED)
def submit(
    data: WritingSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WritingResult:
    """UC-37 — nộp bài & nhận nhận xét (không có LLM thì chấm heuristic)."""
    return writing_service.submit(db, current_user, data)


@router.get("/writing/submissions", response_model=list[WritingResult])
def list_submissions(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WritingResult]:
    """UC-37 — các bài đã nộp, mới nhất trước."""
    return writing_service.list_submissions(db, current_user, limit)


@router.get("/notes", response_model=list[NoteRow])
def list_notes(
    q: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[NoteRow]:
    """UC-38 — sổ tay câu (lọc theo từ khóa nếu có `q`)."""
    return writing_service.list_notes(db, current_user, q)


@router.post("/notes", response_model=NoteRow, status_code=status.HTTP_201_CREATED)
def create_note(
    data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteRow:
    """UC-38 — lưu một câu vào sổ tay."""
    return NoteRow.model_validate(writing_service.create_note(db, current_user, data))


@router.patch("/notes/{note_id}", response_model=NoteRow)
def update_note(
    note_id: int,
    data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteRow:
    """UC-38 — sửa ghi chú."""
    return NoteRow.model_validate(writing_service.update_note(db, current_user, note_id, data))


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-38 — xóa khỏi sổ tay."""
    writing_service.delete_note(db, current_user, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
