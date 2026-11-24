"""UC-94 — trò chơi từ vựng: danh mục, nộp điểm, bảng xếp hạng."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.game import (
    GameDefinition,
    GameLeaderboardRow,
    GameScoreRequest,
    GameScoreResult,
)
from app.services import game_service

router = APIRouter()


def _known_game(key: str):
    game = game_service.get_game(key)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Không có trò chơi '{key}'")
    return game


@router.get("", response_model=list[GameDefinition])
def list_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GameDefinition]:
    """Danh mục trò chơi kèm kỷ lục cá nhân."""
    return game_service.list_games(db, current_user)


@router.post("/{key}/scores", response_model=GameScoreResult)
def submit_score(
    key: str,
    data: GameScoreRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GameScoreResult:
    """Nộp điểm một ván. Chỉ nâng kỷ lục khi cao hơn; số ván luôn tăng."""
    _known_game(key)
    return game_service.submit_score(db, current_user, key, data.score)


@router.get("/{key}/leaderboard", response_model=list[GameLeaderboardRow])
def leaderboard(
    key: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GameLeaderboardRow]:
    _known_game(key)
    return game_service.leaderboard(db, key, limit)
