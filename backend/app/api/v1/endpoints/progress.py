from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.progress import MasteryHistory, ProgressResponse
from app.services import progress_service

router = APIRouter()


@router.get("", response_model=ProgressResponse)
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProgressResponse:
    """UC-40 — tiến độ học + phân bố mastery + từ điểm yếu."""
    return progress_service.get_progress(db, current_user)


@router.get("/items/{item_id}/mastery-history", response_model=MasteryHistory)
def mastery_history(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MasteryHistory:
    """UC-92 — đường cong mastery của một từ theo thời gian."""
    return progress_service.mastery_history(db, current_user, item_id)
