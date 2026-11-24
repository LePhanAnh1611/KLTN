"""Pilot — bài kiểm tra cuối để kiểm chứng mastery của DKT."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.validation import ValidationStart, ValidationStatus
from app.services import validation_service

router = APIRouter()


@router.get("/status", response_model=ValidationStatus)
def get_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationStatus:
    return validation_service.get_status(db, current_user)


@router.post("/start", response_model=ValidationStart)
def start(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationStart:
    """Bốc đề và mở phiên; gọi lại khi đang dở thì trả các câu còn lại.
    Trả lời qua POST /sessions/{id}/answer, nộp bài qua /sessions/{id}/complete."""
    return validation_service.start(db, current_user)
