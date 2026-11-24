"""UC-64 — Suy luận & cập nhật knowledge state (mastery) qua DKT.

Sau mỗi câu trả lời, dựng lịch sử tương tác của user (word, correct) theo thời gian,
gọi service DKT ước lượng P(correct) cho item vừa học, rồi upsert KNOWLEDGE_STATE.
Best-effort: AI lỗi / từ ngoài vocab (mastery=None) -> bỏ qua, KHÔNG chặn luồng học
(BR-05: INTERACTION vẫn là nguồn sự thật). Cold-start (None) xử lý ở UC-69.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.models.interaction import Interaction, counted_interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.user import User
from app.models.word_set import WordSet
from app.services import config_service, dkt_client

logger = logging.getLogger(__name__)

# Có HAI tầm nhìn khác nhau, đừng nhầm:
#  - LSTM chỉ đọc `max_seq_len` = 200 bước gần nhất;
#  - nhưng ĐẶC TRƯNG LỊCH SỬ (đã gặp bao nhiêu lần, lần gần nhất cách bao xa)
#    lúc huấn luyện được tính trên TOÀN chuỗi của người học rồi mới cắt cửa sổ.
# Gửi đúng 200 lượt là ép service đếm thiếu: người học 1.300 lượt sẽ bị đối xử
# như người mới. Gửi rộng hơn để service tính đủ rồi tự cắt.
HISTORY_LIMIT = 1000

# UC-69 cold-start: prior theo độ khó bộ từ (BR-10).
COLD_START_PRIOR = {"beginner": 0.6, "intermediate": 0.5, "advanced": 0.4}
DEFAULT_PRIOR = 0.5


def mastered_threshold() -> float:
    """Ngưỡng mastery của BR-01; điều kiện đầy đủ ở mastered_condition()."""
    return config_service.get_float("mastered_threshold")


def mastered_condition() -> ColumnElement[bool]:
    """BR-01: the same learner/item must have enough correct interactions."""
    correct_count = select(func.count(Interaction.id)).where(
        Interaction.user_id == KnowledgeState.user_id,
        Interaction.item_id == KnowledgeState.item_id,
        Interaction.is_correct.is_(True),
        counted_interaction(),
    ).correlate(KnowledgeState).scalar_subquery()
    return and_(
        KnowledgeState.mastery >= mastered_threshold(),
        correct_count >= config_service.get_int("mastered_min_correct"),
    )


def mastered_item_ids(db: Session, user_id: int) -> set[int]:
    return set(db.execute(select(KnowledgeState.item_id)
        .join(Item, Item.id == KnowledgeState.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(KnowledgeState.user_id == user_id, WordSet.owner_id == user_id,
               Item.deleted_at.is_(None), WordSet.deleted_at.is_(None),
               mastered_condition())
    ).scalars().all())


def cold_start_prior(difficulty: str | None) -> float:
    """Mastery prior cho item chưa có tín hiệu DKT (từ ngoài vocab SLAM / người mới)."""
    return COLD_START_PRIOR.get(difficulty or "", DEFAULT_PRIOR)


def build_history(
    db: Session, user_id: int, limit: int = HISTORY_LIMIT
) -> tuple[list[tuple[str, int]], list[str], dict[str, str]]:
    """Lịch sử gần nhất, theo thời gian tăng dần.

    Trả `([(word, correct)...], [dạng bài...], {từ: từ loại})`.

    Cả **dạng bài** lẫn **từ loại** đều là đặc trưng của mô hình, và phải gửi cho
    MỌI bước chứ không riêng từ đang chấm. Lúc huấn luyện mọi bước đều có đủ hai
    thứ; gửi thiếu là lệch ngay ở đầu vào. Đo bằng phép tự kiểm của service:
    thiếu từ loại ở phần lịch sử làm AUC tụt từ 0,8444 xuống 0,7604 — tám điểm,
    mà không có lỗi nào hiện ra.
    """
    rows = db.execute(
        select(
            Item.word, Interaction.is_correct, Interaction.exercise_format,
            Item.part_of_speech,
        )
        .join(Item, Item.id == Interaction.item_id)
        .where(Interaction.user_id == user_id, counted_interaction())
        .order_by(Interaction.answered_at.desc())
        .limit(limit)
    ).all()
    ordered = list(reversed(rows))
    return (
        [(word, int(correct)) for word, correct, _, _ in ordered],
        [fmt or "" for _, _, fmt, _ in ordered],
        {word: pos for word, _, _, pos in ordered if pos},
    )


def _upsert_mastery(db: Session, user_id: int, item_id: int, mastery: float) -> None:
    ks = db.execute(
        select(KnowledgeState).where(
            KnowledgeState.user_id == user_id, KnowledgeState.item_id == item_id
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if ks is None:
        db.add(KnowledgeState(user_id=user_id, item_id=item_id, mastery=mastery, last_updated=now))
    else:
        ks.mastery = mastery
        ks.last_updated = now
    db.commit()


def predict_before_answer(
    db: Session, user_id: int, item: Item, exercise_format: str | None = None
) -> tuple[float | None, str | None]:
    """UC-70 — dự đoán của mô hình NGAY TRƯỚC khi thấy kết quả lượt này.

    Gọi DKT với (1) toàn bộ lịch sử đến hết lượt TRƯỚC — lượt hiện tại chưa được
    ghi nên tự nhiên không lọt vào — và (2) đúng dạng bài của lượt hiện tại.
    Đây chính là giao thức "dự đoán bước kế tiếp" dùng khi huấn luyện và khi đo
    AUC offline, nên số đo online so thẳng được với số offline.

    Vì sao KHÔNG đọc lại `KNOWLEDGE_STATE.mastery` như bản trước (đổi 2026-10-13):
    giá trị đó được tính ở lần gần nhất người học gặp CHÍNH từ này, rồi đứng yên
    trong khi họ trả lời các từ khác. DKT là mô hình chuỗi — mọi câu trả lời đều
    đổi trạng thái ẩn — nên con số lưu sẵn bị cũ. Đo trên một phiên giả lập 45
    lượt: lệch so với dự đoán tươi trung bình 0,13, tối đa 0,67, chỉ trong vài
    phút. Nó còn được tính cho dạng bài của lần trước, và không tồn tại ở lần
    gặp đầu tiên (mất ~1/3 số lượt), dù bản feature-based chấm được từ chưa gặp.

    Trả `(p, "model")`, hoặc `(None, None)` khi service không trả được số (lỗi,
    tắt, hoặc bản theo ID gặp từ ngoài vocab). KHÔNG rơi về prior: prior là hằng
    số cold-start, không phải dự đoán, và trộn vào thì UC-70 chấm nhầm đối tượng.
    Best-effort: lỗi ở đây không được chặn việc ghi câu trả lời (BR-05).
    """
    try:
        history, formats, history_pos = build_history(db, user_id)
        p = dkt_client.predict_mastery(
            history, [item.word],
            pos={**history_pos, item.word: item.part_of_speech or ""},
            history_formats=formats,
            target_format=exercise_format,
        ).get(item.word)
    except Exception:
        logger.exception("predict_before_answer failed for user %s item %s", user_id, item.id)
        return None, None
    if p is None:
        return None, None
    return float(p), "model"


def update_mastery_for_item(
    db: Session, user: User, item: Item, exercise_format: str | None = None
) -> float | None:
    """Cập nhật mastery cho 1 item vừa học. Trả mastery mới (hoặc None nếu bỏ qua).
    Best-effort: AI lỗi không làm hỏng phiên học.

    - DKT có tín hiệu (từ trong vocab SLAM) -> lưu mastery thật.
    - DKT None (từ ngoài vocab / service lỗi) -> UC-69 cold-start: đặt prior theo
      độ khó bộ từ, NHƯNG chỉ khi chưa có KNOWLEDGE_STATE (không ghi đè giá trị cũ).
    """
    try:
        history, formats, history_pos = build_history(db, user.id)
        mastery = dkt_client.predict_mastery(
            history, [item.word],
            pos={**history_pos, item.word: item.part_of_speech or ""},
            history_formats=formats,
            target_format=exercise_format,
        ).get(item.word)
        if mastery is not None:
            _upsert_mastery(db, user.id, item.id, mastery)
            return mastery

        # cold-start: chỉ khởi tạo prior nếu item chưa có knowledge state
        existing = db.execute(
            select(KnowledgeState).where(
                KnowledgeState.user_id == user.id, KnowledgeState.item_id == item.id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.mastery  # giữ nguyên giá trị đã có
        difficulty = db.execute(
            select(WordSet.difficulty).where(WordSet.id == item.word_set_id)
        ).scalar_one_or_none()
        prior = cold_start_prior(difficulty)
        _upsert_mastery(db, user.id, item.id, prior)
        return prior
    except Exception:
        db.rollback()  # AI lỗi không được làm hỏng phiên học
        return None
