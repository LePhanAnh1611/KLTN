"""UC-32 — đánh dấu từ khó."""
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.item_flag import FlaggedItem, FlagRequest, FlagResponse
from app.services import item_flag_service

router = APIRouter()


@router.get("/flagged-items", response_model=list[FlaggedItem])
def list_flagged(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FlaggedItem]:
    """UC-32 — các từ bạn tự đánh dấu là khó, kèm mastery để đối chiếu."""
    return item_flag_service.list_flagged(db, current_user)


@router.put("/flagged-items/{item_id}", response_model=FlagResponse)
def set_flag(
    item_id: int,
    data: FlagRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FlagResponse:
    """UC-32 — đánh dấu từ (gửi lại = cập nhật ghi chú)."""
    return FlagResponse.model_validate(
        item_flag_service.set_flag(db, current_user, item_id, data)
    )


@router.delete("/flagged-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_flag(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """UC-32 — bỏ đánh dấu."""
    item_flag_service.clear_flag(db, current_user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
