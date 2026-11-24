"""UC-66 — Lập lịch ôn tập, nhắm MỨC NHỚ MỤC TIÊU (DKT-driven).

Bản viết lại sau thí nghiệm UC-93. Luật cũ (`mastery_to_interval_days`) tra
mastery vào bảng bậc {1, 2, 4, 7} ngày, và nó **thua SM-2 ở cả sáu kịch bản mô
phỏng**, chênh −0,72 đến −19,51 từ/người, không khoảng tin cậy nào chứa 0.

Lỗi của luật cũ nằm ở chỗ căn bản: mastery là **P(trả lời đúng ngay bây giờ)**,
một đại lượng không phụ thuộc thời gian, nhưng nó bị dùng để quyết định *bao giờ
quay lại*. Số đo xác nhận: lịch cũ quay lại muộn hơn SM-2 (8,85 ngày so với
7,83) và bắt gặp từ ở mức nhớ thấp hơn hẳn (0,164 so với 0,237) — nó đến khi từ
đã rơi mất.

Luật mới giữ một ước lượng **nửa đời** `h` (số ngày để xác suất nhớ còn một nửa)
cho từng cặp (người, từ), rồi đặt lịch tại `t = h · log2(1/mục_tiêu)` — quay lại
đúng lúc xác suất nhớ tụt tới mức mục tiêu (mặc định 0,90, chỉnh ở UC-81).

DKT giữ đúng vai trò nó giỏi và đã đo được (AUC 0,8382): ước lượng người này nắm
từ này đến đâu. Con số đó điều biến tốc độ giãn của `h`. Nó KHÔNG bị hỏi "bao giờ
thì quên" — câu mà nó chưa từng được huấn luyện để trả lời, và không thể học từ
SLAM vì trong dữ liệu ấy thời điểm ôn do chính bộ lập lịch của Duolingo chọn.

Kết quả mô phỏng của luật mới: thắng SM-2 ở cả sáu kịch bản, +2,27 đến +13,64
từ/người, thắng ở 84–100% người học. Chi tiết và GIỚI HẠN của phép đo:
`docs/UC-93_So_sanh_lich_on_DKT_va_SM2.md`.
"""
from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.clock import user_zone

from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.review import ReviewCalendar, ReviewItem, WeakReviewItem
from app.services import config_service, dkt_client, placement_service
from app.services.mastery_service import build_history, cold_start_prior
from app.models.interaction import Interaction
from app.models.session import StudySession
from app.models.placement import CEFR_LEVELS


#: Sàn/trần cho ước lượng nửa đời và cho khoảng cách ôn. Nửa đời về 0 làm lịch
#: kẹt vĩnh viễn ở "ngay lập tức"; không có trần thì một chuỗi đúng dài đẩy lịch
#: ra hàng năm, xa hơn cả quãng dữ liệu từng quan sát được.
MIN_HALF_LIFE_DAYS = 0.5
MAX_HALF_LIFE_DAYS = 365.0
MAX_INTERVAL_DAYS = 180


def weak_threshold() -> float:
    """UC-86: dưới ngưỡng này thì từ được coi là điểm yếu (Admin chỉnh ở UC-81)."""
    return config_service.get_float("weak_mastery_threshold")


def weak_session_size() -> int:
    """UC-86: số từ tối đa lấy vào một phiên ôn điểm yếu."""
    return config_service.get_int("weak_session_size")


def review_threshold() -> float:
    """θ_review (BR-02): dưới ngưỡng thì cần ôn sớm (Admin chỉnh ở UC-81)."""
    return config_service.get_float("review_threshold")


def mastery_to_interval_days(mastery: float) -> int:
    """LUẬT CŨ, giữ lại làm mốc so sánh cho chương thực nghiệm (UC-93).

    KHÔNG dùng để lập lịch nữa — xem `next_half_life` / `schedule_review`. Nhánh
    `dkt` trong `ml/src/schedule_sim.py` mô phỏng đúng hàm này, và
    `backend/tests/test_scheduler_experiment.py` so từng bậc để hai bên không
    trôi khỏi nhau.
    """
    if mastery < review_threshold():
        return 1          # chưa nắm -> ôn ngày mai
    if mastery < 0.75:
        return 2
    if mastery < 0.9:
        return 4
    return 7              # đã thuộc (BR-01) -> ôn thưa


def target_retention() -> float:
    """Mức nhớ mong muốn tại thời điểm ôn lại (UC-81)."""
    return config_service.get_float("target_retention")


def next_half_life(previous: float | None, mastery: float, is_correct: bool) -> float:
    """Nửa đời mới (ngày) sau một lượt trả lời.

    `previous=None` (lần đầu) -> lấy giá trị khởi đầu từ cấu hình. Nhớ được thì
    giãn theo hệ số nền nhân với `(0.5 + mastery)`: từ mà DKT thấy người này nắm
    chắc sẽ giãn nhanh hơn. Quên thì co lại, nhưng có SÀN — về 0 là lịch ôn kẹt
    ở mức "ngay lập tức" vĩnh viễn.
    """
    h = config_service.get_float("half_life_start_days") if previous is None else previous
    if is_correct:
        h = h * config_service.get_float("half_life_growth") * (0.5 + mastery)
    else:
        h = h * config_service.get_float("half_life_shrink")
    return max(MIN_HALF_LIFE_DAYS, min(MAX_HALF_LIFE_DAYS, h))


def half_life_to_interval_days(half_life: float) -> int:
    """Quay lại đúng lúc P(nhớ) tụt tới mục tiêu: 2^(-t/h) = mục tiêu."""
    interval = half_life * math.log2(1.0 / target_retention())
    return max(1, min(MAX_INTERVAL_DAYS, round(interval)))


def schedule_review(db: Session, user_id: int, item_id: int, mastery: float,
                    is_correct: bool | None = None) -> ReviewSchedule:
    """Upsert REVIEW_SCHEDULE cho (user, item) theo luật nhắm mức nhớ mục tiêu.

    `is_correct=None`: gọi từ chỗ chỉ biết mastery mới chứ không biết kết quả một
    lượt cụ thể (ví dụ tính lại hàng loạt). Khi đó suy từ mastery so với ngưỡng
    cần ôn, thay vì đoán bừa là đúng — đoán đúng sẽ giãn lịch của một từ mà người
    học có thể vừa trả lời sai.
    """
    rs = db.execute(
        select(ReviewSchedule).where(
            ReviewSchedule.user_id == user_id, ReviewSchedule.item_id == item_id
        )
    ).scalar_one_or_none()

    correct = mastery >= review_threshold() if is_correct is None else is_correct
    half_life = next_half_life(rs.half_life_days if rs else None, mastery, correct)
    interval = half_life_to_interval_days(half_life)
    next_at = datetime.now(timezone.utc) + timedelta(days=interval)

    if rs is None:
        rs = ReviewSchedule(
            user_id=user_id, item_id=item_id, next_review_at=next_at,
            interval_days=interval, half_life_days=half_life,
        )
        db.add(rs)
    else:
        rs.next_review_at = next_at
        rs.interval_days = interval
        rs.half_life_days = half_life
    rs.is_paused = False
    db.commit()
    return rs


def _query_schedules(db: Session, user: User):
    """REVIEW_SCHEDULE của user, join item (chưa xóa) + bộ từ (sở hữu, chưa xóa)."""
    return db.execute(
        select(ReviewSchedule, Item, WordSet)
        .join(Item, Item.id == ReviewSchedule.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            ReviewSchedule.user_id == user.id,
            ReviewSchedule.is_paused.is_(False),
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
            WordSet.owner_id == user.id,
        )
        .order_by(ReviewSchedule.next_review_at.asc())
    ).all()


def _to_item(rs: ReviewSchedule, item: Item, ws: WordSet) -> ReviewItem:
    return ReviewItem(
        item_id=item.id, word=item.word, meaning=item.meaning,
        word_set_id=ws.id, word_set_name=ws.name,
        next_review_at=rs.next_review_at, interval_days=rs.interval_days,
    )


def _lower_level(ws: WordSet, entry: str) -> bool:
    return ws.cefr_level in CEFR_LEVELS and CEFR_LEVELS.index(ws.cefr_level) < CEFR_LEVELS.index(entry)


def pause_lower_level_reviews(db: Session, user: User) -> int:
    # Only schedules owned by this learner. Mastery/history are not edited.
    entry = placement_service.entry_level(db, user)
    rows = _query_schedules(db, user)
    count = 0
    for rs, item, ws in rows:
        if _lower_level(ws, entry):
            rs.is_paused = True
            count += 1
    db.commit()
    return count


def get_calendar(db: Session, user: User) -> ReviewCalendar:
    # Build a workload plan, leaving the retention algorithm's due dates intact.
    now = datetime.now(timezone.utc)
    zone = user_zone(db, user.id)
    today = now.astimezone(zone).date()
    day_start = datetime.combine(today, time.min, zone).astimezone(timezone.utc)
    day_end = datetime.combine(today + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    reviewed = set(db.execute(select(Interaction.item_id).join(
        StudySession, StudySession.id == Interaction.session_id
    ).where(Interaction.user_id == user.id, StudySession.mode == "srs_review",
            StudySession.practice_only.is_(False), Interaction.answered_at >= day_start,
            Interaction.answered_at < day_end)).scalars())
    cap = config_service.get_int("review_daily_limit")
    entry = placement_service.entry_level(db, user)
    rows = _query_schedules(db, user)
    lower_count = sum(_lower_level(ws, entry) for rs, item, ws in rows)
    rows = [(rs, item, ws) for rs, item, ws in rows if item.id not in reviewed]
    ids = [item.id for rs, item, ws in rows]
    stored = dict(db.execute(select(KnowledgeState.item_id, KnowledgeState.mastery).where(
        KnowledgeState.user_id == user.id, KnowledgeState.item_id.in_(ids)
    )).all()) if ids else {}
    history, formats, history_pos = build_history(db, user.id)
    preds = dkt_client.predict_mastery(history, [item.word for rs, item, ws in rows],
        pos={**history_pos, **{item.word: item.part_of_speech or "" for rs, item, ws in rows}},
        history_formats=formats, target_format=None) if rows else {}
    def score(item, ws):
        value = preds.get(item.word)
        if value is None:
            value = stored.get(item.id, cold_start_prior(ws.difficulty))
        return max(0.0, min(1.0, float(value)))
    rows.sort(key=lambda row: (max(today, row[0].next_review_at.astimezone(zone).date()),
                              score(row[1], row[2]), row[0].next_review_at, row[1].id))
    used = {today: min(cap, len(reviewed))}
    today_l, tomorrow_l, week_l = [], [], []
    backlog = 0
    for rs, item, ws in rows:
        due_day = rs.next_review_at.astimezone(zone).date()
        day = max(today, due_day)
        while used.get(day, 0) >= cap:
            day += timedelta(days=1)
        used[day] = used.get(day, 0) + 1
        ri = _to_item(rs, item, ws)
        ri.scheduled_for = day
        ri.mastery = round(score(item, ws), 4)
        # A cold-start prior alone is insufficient to mark a word red.
        ri.at_risk = (preds.get(item.word) is not None or item.id in stored) and ri.mastery < weak_threshold()
        if due_day <= today and day > today:
            backlog += 1
        if day == today:
            today_l.append(ri)
        elif day == today + timedelta(days=1):
            tomorrow_l.append(ri)
        elif day <= today + timedelta(days=7):
            week_l.append(ri)
    return ReviewCalendar(today=today_l, tomorrow=tomorrow_l, this_week=week_l,
        daily_limit=cap, reviewed_today=len(reviewed), backlog_count=backlog,
        estimated_minutes=math.ceil(len(today_l) * config_service.get_int("review_seconds_per_word") / 60),
        lower_level_count=lower_count, entry_level=entry)


def get_due_items(db: Session, user: User, limit: int | None = None) -> list[ReviewItem]:
    rows = get_calendar(db, user).today
    return rows[:limit] if limit is not None else rows


def get_weak_items(db: Session, user: User, limit: int | None = None) -> list[WeakReviewItem]:
    """UC-86 — các từ mastery thấp nhất trong thư viện, để mở một phiên ôn đúng chỗ yếu.

    Khác `get_due_items`: KHÔNG lọc theo lịch ôn. Một từ vừa trả lời sai hôm nay
    có next_review_at ở ngày mai nên không "đến hạn", nhưng nó chính là chỗ cần
    ôn nhất — đó là lý do endpoint này tồn tại tách khỏi UC-33.

    Chỉ dựa trên KNOWLEDGE_STATE đã lưu (UC-64), không gọi lại DKT: người học bấm
    "Ôn điểm yếu" là muốn vào học ngay, không phải chờ mô hình chấm lại cả thư viện.
    """
    rows = db.execute(
        select(KnowledgeState.mastery, Item.id, Item.word, Item.meaning, WordSet.id, WordSet.name)
        .join(Item, Item.id == KnowledgeState.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .outerjoin(ReviewSchedule, (ReviewSchedule.item_id == Item.id) & (ReviewSchedule.user_id == user.id))
        .where(
            or_(ReviewSchedule.id.is_(None), ReviewSchedule.is_paused.is_(False)),
            KnowledgeState.user_id == user.id,
            KnowledgeState.mastery < weak_threshold(),
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
            WordSet.owner_id == user.id,
        )
        .order_by(KnowledgeState.mastery.asc(), Item.id.asc())
        .limit(limit or weak_session_size())
    ).all()

    return [
        WeakReviewItem(
            item_id=item_id, word=word, meaning=meaning,
            word_set_id=ws_id, word_set_name=ws_name, mastery=round(float(mastery), 4),
        )
        for mastery, item_id, word, meaning, ws_id, ws_name in rows
    ]
