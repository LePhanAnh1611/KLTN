from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.quiz import QuizQuestion
from app.schemas.session import (
    ActiveSessionResponse,
    AnswerRequest,
    QuizForItemsRequest,
    ResumableSession,
    SessionCreateRequest,
    SessionHistoryResponse,
    SessionResponse,
    SessionSummary,
)
from app.services import quiz_service, session_service

router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    data: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return session_service.create_session(db, current_user, data)


@router.post("/quiz-questions", response_model=list[QuizQuestion])
def quiz_questions_for_items(
    data: QuizForItemsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuizQuestion]:
    """Pilot — câu chọn nghĩa cho các từ của phiên 'Học thông minh' / 'Ôn tập'."""
    return quiz_service.generate_quiz_for_items(db, current_user, data.item_ids)


@router.get("/history", response_model=SessionHistoryResponse)
def get_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    mode: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionHistoryResponse:
    """UC-45 — nhật ký học tập (phiên đã kết thúc), mới nhất trước."""
    return session_service.get_history(
        db, current_user, page=page, page_size=page_size, mode=mode
    )


@router.get("/resume", response_model=ResumableSession | None)
def get_resumable(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumableSession | None:
    """UC-31 — phiên đang dở gần nhất (null nếu không có), cho lối tắt ở trang chủ."""
    return session_service.get_resumable(db, current_user)


@router.get("/active", response_model=ActiveSessionResponse)
def get_active_session(
    word_set_id: int | None = None,
    mode: str | None = Query(default=None, max_length=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActiveSessionResponse:
    """Phiên dở của một bộ (`word_set_id`), hoặc phiên xuyên thư viện theo `mode`."""
    if word_set_id is None and mode is None:
        raise HTTPException(status_code=422, detail="Cần word_set_id hoặc mode")
    return session_service.get_active_session(db, current_user, word_set_id, mode)


@router.post("/{session_id}/answer", status_code=status.HTTP_204_NO_CONTENT)
def record_answer(
    session_id: int,
    data: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session_service.record_answer(db, current_user, session_id, data)


@router.post("/{session_id}/complete", response_model=SessionSummary)
def complete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionSummary:
    return session_service.complete_session(db, current_user, session_id)


@router.post("/{session_id}/abandon", status_code=status.HTTP_204_NO_CONTENT)
def abandon_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session_service.abandon_session(db, current_user, session_id)
