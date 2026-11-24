"""UC-11 — Kiểm tra trình độ đầu vào (placement test)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.placement import (
    PlacementQuestionOut,
    PlacementResult,
    PlacementStatus,
    PlacementSubmit,
)
from app.services import placement_service

router = APIRouter()


@router.get("/status", response_model=PlacementStatus)
def get_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlacementStatus:
    """Đã làm placement chưa + trình độ đầu vào hiện tại."""
    return placement_service.get_status(db, current_user)


@router.get("/questions", response_model=list[PlacementQuestionOut])
def get_questions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PlacementQuestionOut]:
    """Bước 1–2 — bộ câu hỏi trải đều các mức CEFR (không kèm đáp án đúng)."""
    placement_service.require_questions(db)
    return placement_service.get_questions(db)


@router.post("/submit", response_model=PlacementResult)
def submit(
    data: PlacementSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlacementResult:
    """Bước 3–5 — chấm bài & ghi nhận trình độ đầu vào (E1: nộp thiếu vẫn chấm)."""
    return placement_service.submit(db, current_user, data)


@router.post("/skip", response_model=PlacementResult)
def skip(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlacementResult:
    """Luồng thay thế 1a — "Tôi mới bắt đầu": bỏ test, nhận mức A1."""
    return placement_service.skip(db, current_user)
