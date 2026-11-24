"""Dữ liệu khởi tạo cho UC-11 (ngân hàng câu hỏi) và UC-84 (chặng lộ trình).

Tách khỏi seed_demo để dùng lại được: đây là NỘI DUNG HỆ THỐNG (Admin quản lý),
không phải dữ liệu người dùng mẫu.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.learning_stage import LearningStage
from app.models.placement import PlacementQuestion
from app.models.user import User
from app.models.word_set import WordSet

# (mức, từ, nghĩa đúng, 3 nghĩa nhiễu)
PLACEMENT_BANK = [
    ("A1", "book", "quyển sách", ["cái bàn", "con mèo", "ngôi nhà"]),
    ("A1", "water", "nước", ["lửa", "đất", "gió"]),
    ("A1", "friend", "bạn bè", ["kẻ thù", "thầy giáo", "hàng xóm"]),
    ("A1", "eat", "ăn", ["ngủ", "chạy", "đọc"]),

    ("A2", "borrow", "mượn", ["cho vay", "mua", "bán"]),
    ("A2", "weather", "thời tiết", ["thời gian", "khí hậu học", "mùa vụ"]),
    ("A2", "invite", "mời", ["từ chối", "trả lời", "nhắc nhở"]),
    ("A2", "cheap", "rẻ", ["đắt", "mới", "hỏng"]),

    ("B1", "deadline", "hạn chót", ["khởi đầu", "kỳ nghỉ", "cuộc họp"]),
    ("B1", "improve", "cải thiện", ["làm hỏng", "giữ nguyên", "trì hoãn"]),
    ("B1", "reliable", "đáng tin cậy", ["đắt đỏ", "hiếm gặp", "nguy hiểm"]),
    ("B1", "afford", "đủ khả năng chi trả", ["từ chối", "vay mượn", "tiết kiệm"]),

    ("B2", "negotiate", "đàm phán", ["phàn nàn", "quảng cáo", "trì hoãn"]),
    ("B2", "significant", "đáng kể", ["không đáng kể", "tạm thời", "ngẫu nhiên"]),
    ("B2", "sustainable", "bền vững", ["tạm bợ", "đắt đỏ", "phức tạp"]),
    ("B2", "acknowledge", "thừa nhận", ["phủ nhận", "phóng đại", "bỏ qua"]),

    ("C1", "hypothesis", "giả thuyết", ["kết luận", "bằng chứng", "quy trình"]),
    ("C1", "correlation", "tương quan", ["nguyên nhân", "sai số", "trung bình"]),
    ("C1", "meticulous", "tỉ mỉ", ["cẩu thả", "vội vàng", "hào phóng"]),
    ("C1", "inevitable", "không thể tránh khỏi", ["hiếm hoi", "tùy chọn", "bất ngờ"]),
]

# (mức, thứ tự, tiêu đề chặng, mô tả bộ từ, độ khó, [(từ, nghĩa)])
def seed_placement_questions(db: Session) -> int:
    """Nạp ngân hàng câu hỏi nếu còn trống. Trả số câu hiện có."""
    existing = db.execute(select(func.count()).select_from(PlacementQuestion)).scalar_one()
    if existing:
        return existing

    db.add_all([
        PlacementQuestion(
            cefr_level=level, word=word, correct_meaning=meaning, distractors=distractors,
        )
        for level, word, meaning, distractors in PLACEMENT_BANK
    ])
    db.commit()
    return len(PLACEMENT_BANK)


CORE_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "vocab_seed_core.json"


ROADMAP_V2_PATH = Path(__file__).resolve().parents[2] / "data" / "vocab_seed_roadmap_v2.json"
ITEM_FIELDS = ("word", "meaning", "phonetic", "part_of_speech", "example", "example_vi",
               "meaning_source", "meaning_confidence", "example_source")


def seed_stages(db: Session, owner: User) -> int:
    """Lộ trình v1 (cắt theo tần suất). Chỉ đụng chặng v1 — chặng v2 do
    `seed_stages_v2` quản lý, không bị tắt nhầm khi đồng bộ v1."""
    payload = json.loads(CORE_SEED_PATH.read_text(encoding="utf-8"))
    existing = list(db.execute(
        select(LearningStage).where(LearningStage.roadmap_version == 1)
    ).scalars())
    by_name = {ws.name: ws for ws in db.execute(select(WordSet).where(
        WordSet.owner_id == owner.id, WordSet.is_public.is_(True),
        WordSet.deleted_at.is_(None), WordSet.origin_set_id.is_(None),
    )).scalars()}
    by_set = {stage.word_set_id: stage for stage in existing}
    active_ids = set()
    orders = {}
    for spec in payload["word_sets"]:
        level = spec.get("cefr")
        if level not in ("A1", "A2", "B1", "B2", "C1", "C2"):
            continue
        if any(item.get("cefr") != level for item in spec["items"]):
            raise ValueError(f"Mixed CEFR levels: {spec['name']}")
        ws = by_name.get(spec["name"])
        if ws is None:
            ws = WordSet(owner_id=owner.id, name=spec["name"],
                         description=spec.get("description"), category=spec["category"],
                         difficulty=spec["difficulty"], cefr_level=level, is_public=True)
            db.add(ws)
            db.flush()
            db.add_all([Item(word_set_id=ws.id, **{key: item.get(key) for key in ITEM_FIELDS})
                        for item in spec["items"]])
        orders[level] = orders.get(level, 0) + 1
        stage = by_set.get(ws.id)
        if stage is None:
            stage = LearningStage(word_set_id=ws.id)
            db.add(stage)
        stage.title = f"{level} \u00b7 Ch\u1eb7ng {orders[level]}"
        stage.cefr_level = level
        stage.order_index = orders[level]
        stage.is_active = True
        active_ids.add(ws.id)
    for stage in existing:
        if stage.word_set_id not in active_ids:
            stage.is_active = False
    db.commit()
    return sum(orders.values())


def seed_stages_v2(db: Session, owner: User) -> int:
    """Lộ trình v2: hai track rời nhau (chủ đề + cốt lõi) — dữ liệu dựng bởi
    `python -m app.scripts.build_roadmap_v2`.

    Chạy lại được: bộ đã có (tra theo tên) không bị tạo lại, nên bản sao và
    lịch sử học trên v2 giữ nguyên. KHÔNG đọc/ghi chặng v1.
    """
    payload = json.loads(ROADMAP_V2_PATH.read_text(encoding="utf-8"))
    existing = list(db.execute(
        select(LearningStage).where(LearningStage.roadmap_version == 2)
    ).scalars())
    by_set = {stage.word_set_id: stage for stage in existing}
    by_name = {ws.name: ws for ws in db.execute(select(WordSet).where(
        WordSet.owner_id == owner.id, WordSet.is_public.is_(True),
        WordSet.deleted_at.is_(None), WordSet.origin_set_id.is_(None),
    )).scalars()}

    active_ids = set()
    for spec in payload["stages"]:
        level = spec["cefr"]
        ws = by_name.get(spec["name"])
        if ws is None:
            ws = WordSet(owner_id=owner.id, name=spec["name"], category=spec["category"],
                         difficulty=spec["difficulty"], cefr_level=level, is_public=True)
            db.add(ws)
            db.flush()
            db.add_all([Item(word_set_id=ws.id, **{key: item.get(key) for key in ITEM_FIELDS})
                        for item in spec["items"]])
        stage = by_set.get(ws.id)
        if stage is None:
            stage = LearningStage(word_set_id=ws.id, roadmap_version=2)
            db.add(stage)
        stage.title = spec["title"]
        stage.cefr_level = level
        stage.order_index = spec["order_index"]
        stage.track = spec["track"]
        stage.topic = spec["topic"]
        stage.is_active = True
        active_ids.add(ws.id)
    for stage in existing:
        if stage.word_set_id not in active_ids:
            stage.is_active = False
    db.commit()
    return len(active_ids)
