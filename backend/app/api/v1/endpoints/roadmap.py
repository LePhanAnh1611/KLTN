"""UC-84 — Lộ trình học cá nhân hóa · UC-85 — nâng cấp trình độ."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.level_up import LevelUpStatus
from app.schemas.roadmap import RoadmapResponse, StageSummary
from app.services import level_up_service, roadmap_service

router = APIRouter()


@router.get("/roadmap", response_model=RoadmapResponse)
def get_roadmap(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoadmapResponse:
    """Bản đồ chặng + trạng thái cá nhân hóa (BR-RM-01..05)."""
    return roadmap_service.get_roadmap(db, current_user)


@router.get("/roadmap/stages/{stage_id}/summary", response_model=StageSummary)
def get_stage_summary(
    stage_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StageSummary:
    """UC-84 — tổng kết một chặng: đã thuộc gì, còn yếu gì, đi tiếp chặng nào."""
    return roadmap_service.get_stage_summary(db, current_user, stage_id)


@router.get("/level-up", response_model=LevelUpStatus)
def level_up_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LevelUpStatus:
    """UC-85 — điều kiện nâng trình độ + đề xuất đang chờ (tạo mới nếu vừa đủ điều kiện)."""
    return level_up_service.get_status(db, current_user)


@router.post("/level-up/{suggestion_id}/accept", response_model=LevelUpStatus)
def accept_level_up(
    suggestion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LevelUpStatus:
    """UC-85 — đồng ý nâng mức; lộ trình sinh lại từ mức mới (E1: đã quyết định -> 409)."""
    return level_up_service.accept(db, current_user, suggestion_id)


@router.post("/level-up/{suggestion_id}/decline", response_model=LevelUpStatus)
def decline_level_up(
    suggestion_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LevelUpStatus:
    """UC-85 — giữ mức hiện tại; hệ thống không hỏi lại cặp mức này (BR-LU-04)."""
    return level_up_service.decline(db, current_user, suggestion_id)
