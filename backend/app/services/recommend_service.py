"""UC-65 — Gợi ý item vừa sức: chọn item có P(đúng) dự đoán ∈ [0.6, 0.8] (BR-03).

Dự đoán mastery mọi item trong bộ bằng DKT (1 lượt), ưu tiên item trong vùng vừa
sức (gần 0.7 nhất); nếu thiếu -> nới ra item gần vùng nhất (UC-27 E1). Item ngoài
vocab SLAM / chưa có tín hiệu -> dùng cold-start prior.
"""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.user import User
from app.schemas.recommend import RecommendedItem
from app.services import config_service, dkt_client
from app.services.mastery_service import build_history, cold_start_prior
from app.services.word_set_service import get_owned_word_set


def suitable_band() -> tuple[float, float, float]:
    """BR-03 vùng vừa sức (cận dưới, cận trên, tâm vùng) — cấu hình ở UC-81."""
    low = config_service.get_float("band_low")
    high = config_service.get_float("band_high")
    return low, high, (low + high) / 2


def score_items(
    db: Session, user: User, items: list[Item], difficulty: str | None
) -> list[tuple[Item, float]]:
    """[(item, mastery dự đoán)] — dự đoán DKT 1 lượt, thiếu tín hiệu thì dùng
    cold-start prior (UC-69).

    Tách riêng để UC-84 (lộ trình) tái dùng cùng một phép chấm mà KHÔNG cần người
    học sở hữu bộ từ; `recommend_items` vẫn giữ nguyên kiểm tra sở hữu của UC-65.
    """
    if not items:
        return []

    history, formats, history_pos = build_history(db, user.id)
    preds = dkt_client.predict_mastery(
        history,
        [it.word for it in items],
        # Từ loại cho CẢ lịch sử lẫn các từ cần chấm — thiếu phần lịch sử làm
        # AUC tụt 8 điểm (đo bằng phép tự kiểm của ml-serve).
        pos={**history_pos, **{it.word: it.part_of_speech or "" for it in items}},
        history_formats=formats,
        # KHÔNG đoán dạng bài sắp ra: hàm này phục vụ cả gợi ý item (UC-65) lẫn
        # đánh giá chặng lộ trình (UC-84), hai chỗ chưa chọn dạng bài nào cả.
        # Bịa một dạng ở đây là bịa luôn một phần dự đoán.
        target_format=None,
    )
    prior = cold_start_prior(difficulty)
    return [(it, prior if preds.get(it.word) is None else preds[it.word]) for it in items]


def count_in_band(scored: list[tuple[Item, float]]) -> int:
    """Số item nằm trong vùng vừa sức (BR-03) — UC-84 dùng cho BR-RM-03."""
    band_low, band_high, _ = suitable_band()
    return sum(1 for _, m in scored if band_low <= m <= band_high)


def recommend_items(db: Session, user: User, word_set_id: int, limit: int = 10) -> list[RecommendedItem]:
    word_set = get_owned_word_set(db, user, word_set_id)
    items = db.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalars().all()

    scored = score_items(db, user, list(items), word_set.difficulty)
    if not scored:
        return []

    band_low, band_high, band_mid = suitable_band()

    in_band = [(it, m) for it, m in scored if band_low <= m <= band_high]
    in_band.sort(key=lambda x: abs(x[1] - band_mid))  # gần tâm vùng trước

    if len(in_band) >= limit:
        chosen = in_band[:limit]
    else:  # nới ngưỡng: bù bằng item gần vùng nhất
        rest = [(it, m) for it, m in scored if not (band_low <= m <= band_high)]
        rest.sort(key=lambda x: min(abs(x[1] - band_low), abs(x[1] - band_high)))
        chosen = in_band + rest[: limit - len(in_band)]

    picks = mix_in_exploration(chosen, scored, config_service.get_float("explore_rate"))

    return [
        RecommendedItem(
            id=it.id, word=it.word, phonetic=it.phonetic, part_of_speech=it.part_of_speech,
            meaning=it.meaning, example=it.example, example_vi=it.example_vi,
            meaning_confidence=it.meaning_confidence, mastery=round(m, 4),
            in_band=band_low <= m <= band_high, selection=reason,
        )
        for it, m, reason in picks
    ]


def mix_in_exploration(
    chosen: list[tuple[Item, float]],
    scored: list[tuple[Item, float]],
    rate: float,
    rng: random.Random | None = None,
) -> list[tuple[Item, float, str]]:
    """Pilot — thay một phần danh sách gợi ý bằng từ chọn NGẪU NHIÊN.

    Vì sao cần: nếu chỉ đưa ra từ có P ∈ [0.6, 0.8] thì mọi dự đoán được kiểm
    chứng đều nằm trong dải đó. Khi ấy không vẽ được biểu đồ hiệu chuẩn trên
    toàn dải 0–1, và AUC bị kéo thấp giả tạo vì dải dự đoán quá hẹp — mô hình
    đang tự chọn dữ liệu để chấm chính nó. Từ thăm dò được chọn đều ngẫu nhiên
    trong phần còn lại của bộ, KHÔNG nhìn vào dự đoán, nên số đo trên chúng
    không thiên lệch.

    Thay vào cuối danh sách (phần ưu tiên thấp nhất) rồi xáo cả danh sách, để
    người học không đoán được từ nào là từ thăm dò.
    """
    rng = rng or random
    picks: list[tuple[Item, float, str]] = [(it, m, "band") for it, m in chosen]
    if rate <= 0 or not chosen:
        return picks

    chosen_ids = {it.id for it, _ in chosen}
    pool = [(it, m) for it, m in scored if it.id not in chosen_ids]
    n_explore = min(max(1, round(len(chosen) * rate)), len(pool))
    if n_explore == 0:
        return picks

    explore = rng.sample(pool, n_explore)
    picks = picks[: len(picks) - n_explore] + [(it, m, "explore") for it, m in explore]
    rng.shuffle(picks)
    return picks
