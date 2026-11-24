"""Tổng hợp dữ liệu cho trang chủ học viên — CHỈ ĐỌC.

Không tạo bảng mới: mọi con số suy ra từ INTERACTION (BR-05), KNOWLEDGE_STATE
(UC-64), REVIEW_SCHEDULE (UC-66) và USER_PROGRESS sẵn có.

Các phép đếm dùng lại hàm của service chuyên trách (`mastered_threshold`,
`compute_level`, `score_items`...) thay vì viết lại, để số liệu ở trang chủ không
bao giờ lệch với trang Tiến độ / Dashboard.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone, tzinfo

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.clock import user_day_bounds, user_zone
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.home import (
    CourseProgress,
    DailyGoal,
    GamificationSummary,
    RecommendedWord,
    ReviewDay,
    StatsOverview,
    TodayRecommendation,
    UpcomingReview,
)
from app.schemas.recommend import RecommendedItem
from app.services import config_service, recommend_service
from app.services.gamification_service import (
    compute_level,
    default_daily_item_goal,
    level_title,
)
from app.services.mastery_service import cold_start_prior, mastered_condition, mastered_item_ids

RECOMMEND_LIMIT = 20
#: Trần số id nhận ở /recommendations/today/items — bằng trần `limit` của /today.
TODAY_ITEMS_MAX = 50


def _owned_items_filter() -> list:
    """Điều kiện dùng chung: item còn sống, thuộc bộ từ còn sống của người học."""
    return [Item.deleted_at.is_(None), WordSet.deleted_at.is_(None)]


def _unseen_items_filter(user: User):
    """Item người học CHƯA từng trả lời — "từ mới" theo BR-03.

    Interaction là nguồn sự thật (BR-05): đã có một lần trả lời là từ đó thuộc
    luồng ôn tập (BR-02/BR-04), không được đưa lại vào "Học từ mới" dù P(đúng)
    dự đoán của nó đang rơi vào vùng vừa sức.
    """
    seen = select(Interaction.item_id).where(Interaction.user_id == user.id)
    return Item.id.notin_(seen)


def _owned_items_query(user: User) -> Select:
    return (
        select(Item)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(WordSet.owner_id == user.id, *_owned_items_filter())
    )


# --- UC-46/47/48: tổng hợp gamification ---------------------------------------

def count_items_done_today(db: Session, user: User) -> int:
    """Số TỪ RIÊNG BIỆT người học đã trả lời hôm nay, theo MÚI GIỜ NGƯỜI HỌC (UC-88).

    Đếm theo item chứ không theo lượt trả lời: trả lời cùng một từ ba lần vẫn chỉ
    tính là một từ trong mục tiêu ngày.
    """
    # Lấy nguyên cặp mốc từ `clock`, KHÔNG tự dựng lại: lấy ngày theo giờ Việt
    # rồi dán tzinfo=UTC vào là ra một khoảng lệch 7 tiếng nằm ở tương lai.
    day_start, day_end = user_day_bounds(db, user.id)

    return db.execute(
        select(func.count(func.distinct(Interaction.item_id))).where(
            Interaction.user_id == user.id,
            Interaction.answered_at >= day_start,
            Interaction.answered_at < day_end,
        )
    ).scalar_one()


def get_daily_goal(db: Session, user: User) -> DailyGoal:
    """UC-10/41 — mục tiêu từ/ngày; chưa đặt thì lấy mặc định từ cấu hình (UC-81)."""
    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one_or_none()
    target = (settings_row.daily_item_goal if settings_row else None) or default_daily_item_goal()

    done = count_items_done_today(db, user)
    return DailyGoal(done=done, target=target, reached=done >= target)


def get_gamification_summary(db: Session, user: User) -> GamificationSummary:
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one_or_none()

    xp = progress.xp if progress else 0
    streak = progress.streak_count if progress else 0
    level, into_level, for_level = compute_level(xp)

    return GamificationSummary(
        xp=xp, level=level, level_title=level_title(level),
        xp_into_level=into_level, xp_for_next_level=for_level,
        streak_count=streak, daily_goal=get_daily_goal(db, user),
    )


# --- UC-40: mức nắm vững ------------------------------------------------------

def get_stats_overview(db: Session, user: User) -> StatsOverview:
    """Mastery đọc từ KNOWLEDGE_STATE đã lưu (do UC-64 sinh) — KHÔNG gọi lại DKT."""
    total_items = db.execute(
        select(func.count()).select_from(Item)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(WordSet.owner_id == user.id, *_owned_items_filter())
    ).scalar_one()

    mastery_values = db.execute(
        select(KnowledgeState.mastery)
        .join(Item, Item.id == KnowledgeState.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            KnowledgeState.user_id == user.id,
            WordSet.owner_id == user.id,
            *_owned_items_filter(),
        )
    ).scalars().all()

    learned = len(mastery_values)
    mastered = len(mastered_item_ids(db, user.id))

    return StatsOverview(
        total_items=total_items,
        mastered=mastered,
        in_progress=learned - mastered,
        not_started=max(total_items - learned, 0),
        mastery_percent=round(mastered / total_items * 100, 1) if total_items else 0.0,
    )


# --- UC-40/41: tiến độ theo bộ từ ---------------------------------------------

def list_course_progress(db: Session, user: User) -> list[CourseProgress]:
    """Bộ từ trong thư viện + % từ đã thuộc của mỗi bộ."""
    total_by_set = dict(db.execute(
        select(Item.word_set_id, func.count(Item.id))
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(WordSet.owner_id == user.id, *_owned_items_filter())
        .group_by(Item.word_set_id)
    ).all())

    mastered_by_set = dict(db.execute(
        select(Item.word_set_id, func.count(Item.id))
        .join(WordSet, WordSet.id == Item.word_set_id)
        .join(KnowledgeState, KnowledgeState.item_id == Item.id)
        .where(
            WordSet.owner_id == user.id,
            KnowledgeState.user_id == user.id,
            mastered_condition(),
            *_owned_items_filter(),
        )
        .group_by(Item.word_set_id)
    ).all())

    started_by_set = dict(db.execute(
        select(Item.word_set_id, func.count(Item.id))
        .join(WordSet, WordSet.id == Item.word_set_id)
        .join(KnowledgeState, KnowledgeState.item_id == Item.id)
        .where(
            WordSet.owner_id == user.id,
            KnowledgeState.user_id == user.id,
            *_owned_items_filter(),
        )
        .group_by(Item.word_set_id)
    ).all())

    word_sets = db.execute(
        select(WordSet)
        .where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
        .order_by(WordSet.created_at.desc(), WordSet.id.desc())
    ).scalars().all()

    result: list[CourseProgress] = []
    for word_set in word_sets:
        total = total_by_set.get(word_set.id, 0)
        mastered = mastered_by_set.get(word_set.id, 0)
        learning = max(started_by_set.get(word_set.id, 0) - mastered, 0)
        result.append(CourseProgress(
            id=word_set.id, name=word_set.name,
            cover_image_url=word_set.cover_image_url,
            cefr_level=word_set.cefr_level,
            total_items=total, mastered_items=mastered, learning_items=learning,
            percent=round(mastered / total * 100, 1) if total else 0.0,
        ))
    return result


# --- UC-65/69: gợi ý từ vừa sức hôm nay ---------------------------------------

def count_new_learned_today(db: Session, user: User) -> int:
    """Số item mà lần trả lời ĐẦU TIÊN của người học rơi vào hôm nay (múi giờ của
    họ). Đọc từ Interaction (BR-05) nên học bằng chế độ nào cũng tính."""
    day_start, day_end = user_day_bounds(db, user.id)
    first_seen = (
        select(func.min(Interaction.answered_at).label("first_at"))
        .where(Interaction.user_id == user.id)
        .group_by(Interaction.item_id)
        .subquery()
    )
    return db.execute(
        select(func.count()).select_from(first_seen).where(
            first_seen.c.first_at >= day_start, first_seen.c.first_at < day_end,
        )
    ).scalar_one()


def get_today_recommendation(
    db: Session, user: User, limit: int = RECOMMEND_LIMIT
) -> TodayRecommendation:
    """Từ có P(đúng) dự đoán nằm TRONG vùng vừa sức (BR-03), xuyên toàn thư viện.

    Khác `recommend_service.recommend_items` (UC-65) ở hai điểm: không giới hạn
    theo một bộ từ, và KHÔNG nới ngưỡng khi thiếu — trang chủ chỉ hiện đúng từ
    trong khoảng, thiếu thì trả danh sách ngắn.

    Service DKT tắt -> `dkt_client` degrade mềm về cold-start prior (UC-69), hàm
    này vẫn trả kết quả và bật cờ `degraded`.
    """
    rows = db.execute(
        select(Item, WordSet.id, WordSet.name, WordSet.difficulty)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(WordSet.owner_id == user.id, _unseen_items_filter(user), *_owned_items_filter())
    ).all()

    band_low, band_high, band_mid = recommend_service.suitable_band()
    new_today = count_new_learned_today(db, user)
    if not rows:
        return TodayRecommendation(
            count=0, band_low=band_low, band_high=band_high, degraded=False, items=[],
            new_learned_today=new_today,
        )

    items = [row[0] for row in rows]
    meta = {row[0].id: (row[1], row[2], row[3]) for row in rows}

    # Chấm điểm theo bộ từ vì cold-start prior phụ thuộc độ khó của bộ (UC-69)
    scored: list[tuple[Item, float]] = []
    by_set: dict[int, list[Item]] = {}
    for item in items:
        by_set.setdefault(meta[item.id][0], []).append(item)
    for word_set_id, group in by_set.items():
        difficulty = meta[group[0].id][2]
        scored.extend(recommend_service.score_items(db, user, group, difficulty))

    # Điểm trùng khít prior của mọi bộ => nhiều khả năng DKT không trả lời được
    priors = {cold_start_prior(meta[item.id][2]) for item, _ in scored}
    degraded = all(any(abs(m - p) < 1e-9 for p in priors) for _, m in scored)

    in_band = [(item, m) for item, m in scored if band_low <= m <= band_high]
    in_band.sort(key=lambda pair: abs(pair[1] - band_mid))

    return TodayRecommendation(
        count=len(in_band),
        band_low=band_low, band_high=band_high, degraded=degraded,
        new_learned_today=new_today,
        items=[
            RecommendedWord(
                item_id=item.id, word=item.word, meaning=item.meaning,
                word_set_id=meta[item.id][0], word_set_name=meta[item.id][1],
                predicted_p=round(m, 4),
            )
            for item, m in in_band[:limit]
        ],
    )


def get_today_study_items(
    db: Session, user: User, item_ids: list[int], rng: random.Random | None = None
) -> list[RecommendedItem]:
    """Nội dung phiên "Học từ mới" mở từ trang chủ — ĐÚNG các từ trang chủ đã gợi ý.

    Trước đây nút "Học N từ mới" chỉ mở màn học của bộ chứa từ đầu tiên, và màn
    học tự gọi `/word-sets/{id}/recommend?limit=20` (một bộ, có nới ngưỡng) — nên
    trang chủ ghi 6 từ mà vào học 20 từ, phần lớn ngoài vùng vừa sức. Hàm này
    KHÔNG chọn lại: chỉ tra dữ liệu cho các id client gửi lên (id không thuộc
    người học thì bỏ qua), giữ nguyên thứ tự trang chủ đã xếp.

    Thăm dò (pilot): vẫn thay một phần danh sách bằng từ chọn NGẪU NHIÊN như
    `recommend_items`, để dữ liệu hiệu chuẩn không chỉ nằm trong dải [0.6, 0.8].
    Phép thay giữ nguyên số lượng, nên số từ học vẫn khớp con số ở trang chủ.
    Pool thăm dò là phần còn lại của thư viện; bốc ngẫu nhiên TRƯỚC rồi mới chấm
    điểm — vừa không nhìn dự đoán khi chọn, vừa khỏi chấm cả thư viện lần nữa.
    """
    rng = rng or random
    wanted = list(dict.fromkeys(item_ids))[:TODAY_ITEMS_MAX]  # bỏ trùng, giữ thứ tự
    if not wanted:
        return []

    rows = db.execute(
        select(Item, WordSet.difficulty)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(WordSet.owner_id == user.id, Item.id.in_(wanted), *_owned_items_filter())
    ).all()
    found = {item.id: (item, difficulty) for item, difficulty in rows}
    chosen_items = [found[i] for i in wanted if i in found]
    if not chosen_items:
        return []

    # Chấm điểm theo độ khó của bộ (cold-start prior phụ thuộc bộ — UC-69)
    def _score(pairs: list[tuple[Item, str | None]]) -> dict[int, float]:
        by_difficulty: dict[str | None, list[Item]] = {}
        for item, difficulty in pairs:
            by_difficulty.setdefault(difficulty, []).append(item)
        out: dict[int, float] = {}
        for difficulty, group in by_difficulty.items():
            out.update({it.id: m for it, m in recommend_service.score_items(db, user, group, difficulty)})
        return out

    scores = _score(chosen_items)
    chosen = [(item, scores[item.id]) for item, _ in chosen_items]

    explore_scored: list[tuple[Item, float]] = []
    rate = config_service.get_float("explore_rate")
    if rate > 0:
        pool_ids = db.execute(
            select(Item.id)
            .join(WordSet, WordSet.id == Item.word_set_id)
            .where(
                WordSet.owner_id == user.id, Item.id.notin_(list(found)),
                _unseen_items_filter(user), *_owned_items_filter(),
            )
        ).scalars().all()
        n_explore = min(max(1, round(len(chosen) * rate)), len(pool_ids))
        if n_explore > 0:
            sampled = rng.sample(list(pool_ids), n_explore)
            pool_rows = db.execute(
                select(Item, WordSet.difficulty)
                .join(WordSet, WordSet.id == Item.word_set_id)
                .where(Item.id.in_(sampled))
            ).all()
            pool_scores = _score([(item, d) for item, d in pool_rows])
            explore_scored = [(item, pool_scores[item.id]) for item, _ in pool_rows]

    # Pool đã bốc đúng n_explore từ => mix_in_exploration lấy hết số đó, thay vào
    # cuối danh sách rồi xáo — y hệt phiên "Học thông minh" của một bộ.
    picks = recommend_service.mix_in_exploration(chosen, explore_scored, rate, rng=rng)

    band_low, band_high, _ = recommend_service.suitable_band()
    return [
        RecommendedItem(
            id=it.id, word=it.word, phonetic=it.phonetic, part_of_speech=it.part_of_speech,
            meaning=it.meaning, example=it.example, example_vi=it.example_vi,
            meaning_confidence=it.meaning_confidence, mastery=round(m, 4),
            in_band=band_low <= m <= band_high, selection=reason,
        )
        for it, m, reason in picks
    ]


# --- UC-36/66: lịch ôn ---------------------------------------------------------

def _month_bounds(month: str, zone: tzinfo = timezone.utc) -> tuple[datetime, datetime]:
    """Local month boundaries converted to UTC for timestamp queries."""
    year_str, _, month_str = month.partition("-")
    year, month_number = int(year_str), int(month_str)
    if not 1 <= month_number <= 12:
        raise ValueError("tháng phải trong khoảng 01-12")

    start = datetime(year, month_number, 1, tzinfo=zone)
    end = (
        datetime(year + 1, 1, 1, tzinfo=zone) if month_number == 12
        else datetime(year, month_number + 1, 1, tzinfo=zone)
    )
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def get_review_days(db: Session, user: User, month: str) -> list[ReviewDay]:
    """Các ngày trong tháng có từ tới hạn ôn + số lượng, để frontend tô lịch."""
    zone = user_zone(db, user.id)
    start, end = _month_bounds(month, zone)

    day = func.date(func.timezone(zone.key, ReviewSchedule.next_review_at))
    rows = db.execute(
        select(day.label("day"), func.count(ReviewSchedule.id))
        .join(Item, Item.id == ReviewSchedule.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            ReviewSchedule.user_id == user.id,
            ReviewSchedule.is_paused.is_(False),
            ReviewSchedule.next_review_at >= start,
            ReviewSchedule.next_review_at < end,
            *_owned_items_filter(),
        )
        .group_by(day)
        .order_by(day)
    ).all()

    return [
        ReviewDay(date=value if isinstance(value, date) else date.fromisoformat(str(value)),
                  due_count=count)
        for value, count in rows
    ]


def list_upcoming_reviews(db: Session, user: User, limit: int = 3) -> list[UpcomingReview]:
    """Vài nhóm ôn sắp tới, gom theo BỘ TỪ, sắp xếp theo thời điểm tăng dần.

    Gồm cả mục đã quá hạn (thời điểm trong quá khứ) — người học cần thấy phần
    đang nợ trước tiên.
    """
    rows = db.execute(
        select(
            WordSet.id, WordSet.name, WordSet.category,
            func.count(ReviewSchedule.id).label("due_count"),
            func.min(ReviewSchedule.next_review_at).label("scheduled_at"),
        )
        .join(Item, Item.id == ReviewSchedule.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(ReviewSchedule.user_id == user.id, ReviewSchedule.is_paused.is_(False), *_owned_items_filter())
        .group_by(WordSet.id, WordSet.name, WordSet.category)
        .order_by(func.min(ReviewSchedule.next_review_at))
        .limit(limit)
    ).all()

    return [
        UpcomingReview(
            id=word_set_id, title=name, group=category,
            due_count=due_count, scheduled_at=scheduled_at,
        )
        for word_set_id, name, category, due_count, scheduled_at in rows
    ]
