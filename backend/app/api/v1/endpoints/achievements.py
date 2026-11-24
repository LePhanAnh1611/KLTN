from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.achievement import AchievementStatus
from app.services import achievement_service

router = APIRouter()


@router.get("", response_model=list[AchievementStatus])
def list_achievements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AchievementStatus]:
    """UC-43 — mọi huy hiệu kèm trạng thái mở khóa của user."""
    return [AchievementStatus(**a) for a in achievement_service.list_with_status(db, current_user)]
