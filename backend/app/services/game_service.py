"""UC-94 — trò chơi từ vựng.

**Trò chơi ở đây không phải lớp trang trí bên ngoài việc học.** Mỗi lượt trả lời
trong trò chơi đi qua đúng luồng phiên học (`session_service.record_answer`), nên
nó ghi INTERACTION đầy đủ (BR-05) và cập nhật mastery qua DKT như mọi dạng bài
khác. Khác biệt duy nhất là áp lực thời gian và cách trình bày.

## Chỗ dễ sai nhất: dạng bài gửi cho mô hình

Mô hình có 4 chiều **dạng bài**, và đo được trên đường phục vụ thật: cùng một
từ, cùng lịch sử, chỉ đổi dạng bài thì P(đúng) lệch tới 10 điểm phần trăm. Ba
trò dưới đây không phải ba dạng bài mới — chúng là ba dạng ĐÃ CÓ, mặc áo khác:

| Trò | Bản chất nhận thức | Dạng bài gửi cho mô hình |
|---|---|---|
| Mưa từ | đọc nghĩa, nhớ chủ động mặt chữ | `typing` |
| Nghe đánh vần | nghe rồi viết lại | `dictation` |
| Ghép cặp tốc độ | nhận diện | `matching` |

Nếu gửi `game_rain` làm dạng bài thì `format_code` không nhận ra và trả mã
"other" — một mã mà mô hình **chưa từng được huấn luyện**. API vẫn 200, mastery
vẫn có số, chỉ là sai. Vì vậy backend KHÔNG tin dạng bài do client gửi cho phiên
trò chơi: nó tự suy từ chế độ phiên (`exercise_format_for_mode`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.game_score import GameScore
from app.models.user import User
from app.schemas.game import GameDefinition, GameLeaderboardRow, GameScoreResult


@dataclass(frozen=True)
class GameDef:
    key: str
    name: str
    description: str
    session_mode: str
    #: Dạng bài THẬT gửi cho DKT — phải là một khóa có trong `FORMAT_ALIASES`
    #: phía ml, nếu không mô hình nhận mã "other" chưa được huấn luyện.
    exercise_format: str
    #: Nguồn đề: endpoint bài tập sẵn có mà frontend gọi lại.
    source: str


GAMES: tuple[GameDef, ...] = (
    GameDef(
        key="rain", name="Mưa từ",
        description="Nghĩa tiếng Việt rơi xuống - gõ từ tiếng Anh trước khi nó chạm đáy.",
        session_mode="game_rain", exercise_format="typing", source="typing",
    ),
    GameDef(
        key="spelling", name="Nghe đánh vần",
        description="Nghe phát âm rồi viết lại đúng chính tả, tính giờ.",
        session_mode="game_spelling", exercise_format="dictation", source="typing",
    ),
    GameDef(
        key="match", name="Ghép cặp tốc độ",
        description="Ghép từ với nghĩa cho hết bảng trước khi hết giờ.",
        session_mode="game_match", exercise_format="matching", source="matching",
    ),
)

_BY_KEY = {g.key: g for g in GAMES}
_BY_MODE = {g.session_mode: g for g in GAMES}

#: Trần điểm mỗi ván. Điểm do client tính nên về nguyên tắc không tin được;
#: trần này chặn một con số vô lý làm hỏng bảng xếp hạng. Nó KHÔNG phải cơ chế
#: chống gian lận thật — muốn chặt thì phải tính điểm ở server, mà điều đó đòi
#: server mô phỏng lại toàn bộ vòng lặp trò chơi.
MAX_SCORE_PER_ROUND = 100_000
LEADERBOARD_SIZE = 20


def get_game(key: str) -> GameDef | None:
    return _BY_KEY.get(key)


def exercise_format_for_mode(mode: str | None) -> str | None:
    """Chế độ phiên trò chơi -> dạng bài thật. None nếu không phải phiên trò chơi."""
    game = _BY_MODE.get(mode or "")
    return game.exercise_format if game else None


def game_session_modes() -> list[str]:
    return [g.session_mode for g in GAMES]


def list_games(db: Session, user: User) -> list[GameDefinition]:
    """Danh mục trò chơi kèm kỷ lục cá nhân."""
    mine = {
        row.game: row
        for row in db.execute(
            select(GameScore).where(GameScore.user_id == user.id)
        ).scalars()
    }
    return [
        GameDefinition(
            key=g.key, name=g.name, description=g.description,
            session_mode=g.session_mode, exercise_format=g.exercise_format,
            source=g.source,
            best_score=mine[g.key].best_score if g.key in mine else None,
            plays=mine[g.key].plays if g.key in mine else 0,
        )
        for g in GAMES
    ]


def submit_score(db: Session, user: User, key: str, score: int) -> GameScoreResult:
    """Ghi nhận một ván. Chỉ nâng kỷ lục khi điểm mới CAO HƠN.

    `plays` luôn tăng, kể cả ván thua: số ván chơi là thước đo mức độ dùng, còn
    kỷ lục là thước đo thành tích — trộn hai thứ vào một con số thì mất cả hai.
    """
    score = max(0, min(int(score), MAX_SCORE_PER_ROUND))
    now = datetime.now(timezone.utc)

    row = db.execute(
        select(GameScore).where(GameScore.user_id == user.id, GameScore.game == key)
    ).scalar_one_or_none()

    if row is None:
        row = GameScore(user_id=user.id, game=key, best_score=score, best_at=now, plays=1)
        db.add(row)
        improved = True
    else:
        row.plays += 1
        improved = score > row.best_score
        if improved:
            row.best_score = score
            row.best_at = now
    db.commit()
    db.refresh(row)

    return GameScoreResult(
        game=key, score=score, best_score=row.best_score,
        is_new_best=improved, plays=row.plays, rank=_rank_of(db, key, row.best_score),
    )


def _rank_of(db: Session, key: str, best_score: int) -> int:
    """Hạng = số người có kỷ lục CAO HƠN, cộng một."""
    higher = db.execute(
        select(func.count()).select_from(GameScore)
        .where(GameScore.game == key, GameScore.best_score > best_score)
    ).scalar_one()
    return int(higher) + 1


def leaderboard(db: Session, key: str, limit: int = LEADERBOARD_SIZE) -> list[GameLeaderboardRow]:
    rows = db.execute(
        select(GameScore.best_score, GameScore.best_at, User.id, User.display_name)
        .join(User, User.id == GameScore.user_id)
        .where(GameScore.game == key, GameScore.best_score > 0)
        .order_by(GameScore.best_score.desc(), GameScore.best_at.asc())
        .limit(limit)
    ).all()
    return [
        GameLeaderboardRow(
            rank=i + 1, user_id=uid, display_name=name, best_score=score, best_at=at,
        )
        for i, (score, at, uid, name) in enumerate(rows)
    ]
