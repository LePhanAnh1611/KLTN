"""UC-44 — Thử thách hôm nay."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.challenge import DailyChallenges
from app.services import challenge_service

router = APIRouter()


@router.get("/challenges/today", response_model=DailyChallenges)
def today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyChallenges:
    """UC-44 — thử thách của hôm nay kèm tiến độ (đọc từ dữ liệu học đã có)."""
    return challenge_service.get_today(db, current_user)


@router.post("/challenges/{code}/claim", response_model=DailyChallenges)
def claim(
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyChallenges:
    """UC-44 — nhận thưởng (E1 mã sai 404, E2 chưa xong 400, E3 nhận rồi 409)."""
    return challenge_service.claim(db, current_user, code)
