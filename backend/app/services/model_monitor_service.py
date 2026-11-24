"""UC-70 — giám sát hiệu năng mô hình DKT trên dữ liệu hệ thống.

Bản viết lại sau đợt rà soát 2026-08-25. Ba khuyết điểm của cách đo cũ, đều
khiến con số **không dùng được cho chương thực nghiệm của khóa luận**:

1. **Vòng lặp tự chứng minh.** Cách cũ so `mastery HIỆN TẠI` của item với kết quả
   các lượt trả lời gần đây — mà chính những lượt đó đã cập nhật con số mastery
   ấy. Đó là hậu nghiệm giải thích lại quan sát sinh ra nó, không phải dự đoán.
   Nay dùng `INTERACTION.predicted_mastery`: dự đoán của mô hình **ngay trước**
   khi thấy kết quả (đánh giá prequential — chuẩn của Knowledge Tracing). Từ
   2026-10-13 con số này được hỏi DKT tươi trước mỗi lượt (xem
   `mastery_service.predict_before_answer`); trước đó nó là KNOWLEDGE_STATE còn
   lại từ lần gặp trước của chính từ đó — đã cũ, và trống ở lần gặp đầu.
   Dữ liệu `prediction_source = 'prior'` chỉ còn ở các lượt ghi trước ngày đó.

2. **Trộn dự đoán của mô hình với giá trị cold-start.** Gần một nửa số từ trong
   hệ thống nằm ngoài vocab của mô hình nên mastery đứng nguyên ở prior. Đưa cả
   đống prior đó vào tính accuracy thì con số đo được chủ yếu là *tỉ lệ người học
   trả lời đúng*, không phải năng lực mô hình. Nay tách hẳn hai tập.

3. **`coverage` lẫn hai chuyện khác nhau.** Công thức cũ `mastery != 0.5` không
   phân biệt "mô hình không biết từ này" với "người học chưa động tới từ này".
   Nay `coverage` chỉ tính trên các state ĐÃ có tương tác, và thêm
   `vocab_coverage` đo thẳng bằng cách hỏi chính service đang phục vụ.

Luôn kèm `baseline_accuracy` (tỉ lệ đúng thực tế = bộ đoán bừa theo lớp đa số):
một mô hình không vượt được baseline thì accuracy cao cũng vô nghĩa.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction, counted_interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.model_metric import ModelMetric
from app.schemas.model_monitor import MetricPoint, ModelHealth
from app.services import dkt_client

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "dkt"
LOOKBACK_DAYS = 7
MIN_SAMPLE = 20          # dưới mức này thì con số không nói lên điều gì
VOCAB_PROBE_SIZE = 200   # số từ lấy mẫu khi đo độ phủ vocab


def _prequential_pairs(db: Session, days: int) -> list[tuple[float, bool]]:
    """[(p̂ trước khi trả lời, kết quả thật)] — CHỈ các lượt do mô hình dự đoán.

    Bỏ `prediction_source = 'prior'` và các lượt chưa có dự đoán: đó là giá trị
    cold-start, đưa vào thì đang chấm điểm hằng số chứ không chấm mô hình.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(Interaction.predicted_mastery, Interaction.is_correct).where(
            Interaction.answered_at >= since,
            counted_interaction(),
            Interaction.predicted_mastery.is_not(None),
            Interaction.prediction_source == "model",
        )
    ).all()
    return [(float(p), bool(c)) for p, c in rows]


def _all_recent_outcomes(db: Session, days: int) -> list[bool]:
    """Kết quả mọi lượt trả lời gần đây — nền để tính baseline."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return [
        bool(c) for (c,) in db.execute(
            select(Interaction.is_correct).where(Interaction.answered_at >= since, counted_interaction())
        ).all()
    ]


def _state_coverage(db: Session) -> tuple[float, int, int]:
    """Tỉ lệ state ĐÃ CÓ TƯƠNG TÁC mà mô hình thực sự chấm được.

    Loại hẳn các state người học chưa động tới: chúng đứng ở prior là chuyện
    đương nhiên, tính vào thì làm loãng con số cần nhìn.
    """
    answered = (
        select(Interaction.user_id, Interaction.item_id)
        .distinct()
        .subquery()
    )
    total = db.execute(
        select(func.count())
        .select_from(KnowledgeState)
        .join(answered,
              (answered.c.user_id == KnowledgeState.user_id)
              & (answered.c.item_id == KnowledgeState.item_id))
    ).scalar_one()
    if not total:
        return 0.0, 0, 0

    from_model = db.execute(
        select(func.count())
        .select_from(KnowledgeState)
        .join(answered,
              (answered.c.user_id == KnowledgeState.user_id)
              & (answered.c.item_id == KnowledgeState.item_id))
        .where(KnowledgeState.mastery != 0.5)
    ).scalar_one()
    return from_model / total, from_model, total


def _vocab_coverage(db: Session, sample_size: int = VOCAB_PROBE_SIZE) -> float | None:
    """Tỉ lệ từ trong thư viện mà service đang phục vụ THỰC SỰ biết.

    Đo bằng cách hỏi thẳng `/predict` chứ không suy từ DB: đây là con đường thật
    mà mọi lượt học đi qua. Lịch sử dò chỉ để service chịu trả lời — cái ta đọc
    là *có/không có* giá trị, không phải độ lớn của nó.

    Trả None khi service không sẵn sàng (đừng báo 0% — dễ đọc nhầm thành
    "mô hình không biết gì").
    """
    words = [
        w for (w,) in db.execute(
            select(Item.word).where(Item.deleted_at.is_(None))
            .distinct().limit(sample_size)
        ).all()
    ]
    if not words:
        return None

    probe = dkt_client.predict_mastery([(words[0], 1)], words)
    if not probe or all(v is None for v in probe.values()):
        # Không phân biệt được "service chết" với "không biết từ nào" -> thử lại
        # bằng một từ chắc chắn phổ thông; vẫn None thì coi như service không sẵn sàng.
        if dkt_client.predict_mastery([("book", 1)], ["book"]).get("book") is None:
            return None
    known = sum(1 for v in probe.values() if v is not None)
    return known / len(words)


def compute_health(db: Session, *, days: int = LOOKBACK_DAYS) -> ModelHealth:
    """Chỉ số sức khỏe mô hình trên dữ liệu gần đây (không ghi DB)."""
    pairs = _prequential_pairs(db, days)
    sample = len(pairs)
    outcomes = _all_recent_outcomes(db, days)

    coverage, covered_states, answered_states = _state_coverage(db)
    vocab_coverage = _vocab_coverage(db)
    baseline = (
        max(sum(outcomes), len(outcomes) - sum(outcomes)) / len(outcomes)
        if outcomes else None
    )

    common = {
        "model_name": DEFAULT_MODEL,
        "lookback_days": days,
        "coverage": round(coverage, 4),
        "covered_states": covered_states,
        "answered_states": answered_states,
        "vocab_coverage": None if vocab_coverage is None else round(vocab_coverage, 4),
        "baseline_accuracy": None if baseline is None else round(baseline, 4),
    }

    if sample < MIN_SAMPLE:
        return ModelHealth(
            sample_size=sample, accuracy=None, brier=None, reliable=False,
            note=(
                f"Cần tối thiểu {MIN_SAMPLE} lượt CÓ dự đoán của mô hình trong "
                f"{days} ngày để đánh giá (hiện {sample}). Lượt rơi vào giá trị "
                "cold-start không được tính."
            ),
            **common,
        )

    hits = sum(1 for p, correct in pairs if (p >= 0.5) == correct)
    brier = sum((p - (1.0 if correct else 0.0)) ** 2 for p, correct in pairs) / sample

    return ModelHealth(
        sample_size=sample,
        accuracy=round(hits / sample, 4), brier=round(brier, 4), reliable=True,
        note=(
            "Đánh giá prequential: dự đoán chốt TRƯỚC khi thấy kết quả, chỉ tính "
            "các lượt do mô hình chấm. So với baseline (đoán theo lớp đa số) để "
            "biết mô hình có thực sự thêm giá trị. Đây vẫn là số đo trên dữ liệu "
            "vận hành, KHÔNG thay cho AUC trên tập test chuẩn ở chương thực nghiệm."
        ),
        **common,
    )


def record_snapshot(db: Session, *, days: int = LOOKBACK_DAYS) -> ModelHealth:
    """Chốt số đo hiện tại vào MODEL_METRIC để vẽ được đường theo thời gian."""
    health = compute_health(db, days=days)
    now = datetime.now(timezone.utc)

    points: dict[str, float | None] = {"coverage": health.coverage}
    if health.vocab_coverage is not None:
        points["vocab_coverage"] = health.vocab_coverage
    if health.baseline_accuracy is not None:
        points["baseline_accuracy"] = health.baseline_accuracy
    if health.reliable:
        points["accuracy"] = health.accuracy
        points["brier"] = health.brier

    for metric, value in points.items():
        if value is None:
            continue
        db.add(ModelMetric(
            model_name=health.model_name, metric=metric, value=float(value),
            sample_size=health.sample_size, recorded_at=now,
        ))
    db.commit()
    return health


def list_history(db: Session, *, metric: str | None = None, limit: int = 100) -> list[MetricPoint]:
    """Chuỗi thời gian đã chốt, cũ -> mới để vẽ biểu đồ."""
    query = select(ModelMetric).order_by(ModelMetric.recorded_at.desc()).limit(limit)
    if metric:
        query = select(ModelMetric).where(ModelMetric.metric == metric)             .order_by(ModelMetric.recorded_at.desc()).limit(limit)

    rows = db.execute(query).scalars().all()
    return [
        MetricPoint(
            metric=r.metric, value=r.value, sample_size=r.sample_size,
            recorded_at=r.recorded_at,
        )
        for r in reversed(rows)
    ]
