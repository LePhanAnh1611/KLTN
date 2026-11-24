"""UC-81 — cấu hình hệ thống chỉnh được lúc chạy.

Gom các ngưỡng trước đây hardcode rải rác (BR-01/02/03, quy đổi XP, số item tối
thiểu...) về một chỗ. Giá trị đọc qua cache tiến trình để các hàm thuần như
`compute_level()` không phải nhận thêm tham số db; cache được cập nhật ngay khi
Admin lưu. Lưu ý: cache theo tiến trình — chạy nhiều worker thì mỗi worker nạp
lại khi khởi động (đủ cho phạm vi khóa luận).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

ValueType = Literal["float", "int", "bool"]


@dataclass(frozen=True)
class ConfigDef:
    key: str
    default: float | int | bool
    value_type: ValueType
    label: str
    description: str
    minimum: float | None = None
    maximum: float | None = None


# Khoảng an toàn (minimum/maximum) phục vụ E1 UC-81: giá trị ngoài khoảng -> chặn.
CONFIG_DEFS: list[ConfigDef] = [
    ConfigDef("mastered_threshold", 0.9, "float", "Ngưỡng 'đã thuộc'",
              "BR-01: mastery đạt ngưỡng VÀ đủ số lần trả lời đúng", 0.5, 1.0),
    ConfigDef("mastered_min_correct", 3, "int", "Số lần đúng tối thiểu để thuộc",
              "BR-01: số lượt trả lời đúng của chính người học trên item này", 1, 100),
    ConfigDef("review_threshold", 0.6, "float", "Ngưỡng cần ôn (θ_review)",
              "BR-02: mastery dưới ngưỡng thì đưa vào hàng đợi ôn", 0.1, 0.95),
    ConfigDef("band_low", 0.6, "float", "Cận dưới vùng vừa sức",
              "BR-03: P(đúng) dự đoán tối thiểu để gợi ý item mới", 0.1, 0.9),
    ConfigDef("band_high", 0.8, "float", "Cận trên vùng vừa sức",
              "BR-03: P(đúng) dự đoán tối đa để gợi ý item mới", 0.2, 0.99),
    ConfigDef("xp_per_correct", 10, "int", "XP mỗi câu đúng",
              "Q5: quy đổi XP khi trả lời đúng", 1, 100),
    ConfigDef("xp_per_level", 100, "int", "XP mỗi cấp",
              "Số XP cần để lên 1 cấp", 10, 10000),
    ConfigDef("default_daily_xp_goal", 50, "int", "Mục tiêu XP/ngày mặc định",
              "UC-41: dùng khi người học chưa tự đặt mục tiêu", 10, 1000),
    ConfigDef("default_daily_item_goal", 10, "int", "Mục tiêu từ/ngày mặc định",
              "UC-10 luồng 1a: dùng khi người học chưa tự đặt mục tiêu", 1, 200),
    ConfigDef("min_items_for_quiz", 4, "int", "Số từ tối thiểu để tạo quiz",
              "Cần 1 đáp án đúng + các đáp án nhiễu", 2, 20),
    ConfigDef("min_items_to_publish", 1, "int", "Số từ tối thiểu để công khai bộ từ vựng",
              "UC-17: điều kiện tối thiểu khi publish", 1, 100),
    ConfigDef("require_post_approval", False, "bool", "Duyệt bài trước khi hiển thị",
              "Q3/UC-77: bật thì bài cộng đồng phải qua kiểm duyệt", None, None),
    ConfigDef("review_daily_limit", 30, "int", "Số từ ôn tối đa mỗi ngày",
              "Phân bổ từ đến hạn theo ưu tiên DKT và dàn tồn đọng sang ngày sau", 1, 200),
    ConfigDef("review_seconds_per_word", 16, "int", "Thời gian ôn dự kiến mỗi từ (giây)",
              "Ước tính thời gian cho thẻ lịch ôn", 1, 120),
    ConfigDef("target_retention", 0.9, "float", "Mức nhớ mục tiêu khi ôn lại",
              "UC-66: đặt lịch sao cho lúc ôn lại, xác suất còn nhớ ~ mức này. "
              "Cao hơn = ôn dày, tốn công nhưng chắc; thấp hơn = ôn thưa, dễ quên",
              0.6, 0.98),
    ConfigDef("half_life_start_days", 2.0, "float", "Nửa đời khởi đầu (ngày)",
              "UC-66: ước lượng nửa đời ngay sau lần học đầu, khi chưa có lịch sử",
              0.5, 30.0),
    ConfigDef("half_life_growth", 1.6, "float", "Hệ số giãn nửa đời khi nhớ được",
              "UC-66: hệ số nền, còn nhân thêm theo mastery mà DKT chấm", 1.05, 4.0),
    ConfigDef("half_life_shrink", 0.5, "float", "Hệ số co nửa đời khi quên",
              "UC-66: trả lời sai thì nửa đời ước lượng còn lại bấy nhiêu", 0.1, 0.95),
    ConfigDef("stage_mastery_high", 0.85, "float", "Ngưỡng mastery của chặng (M_high)",
              "BR-RM-01: item được tính là nắm vững trong chặng lộ trình", 0.5, 1.0),
    ConfigDef("stage_mastered_ratio", 0.8, "float", "Tỉ lệ item để chặng 'đã thuộc'",
              "BR-RM-01: tỉ lệ item đạt M_high để coi chặng là hoàn thành", 0.3, 1.0),
    ConfigDef("require_email_verification", False, "bool", "Bắt buộc xác thực email",
              "UC-03/UC-04 E3: bật thì chưa xác thực email sẽ không đăng nhập được", None, None),
    ConfigDef("placement_pass_ratio", 0.6, "float", "Tỉ lệ đúng để qua một mức CEFR",
              "UC-11: tỉ lệ trả lời đúng tối thiểu để công nhận mức đó", 0.3, 1.0),
    ConfigDef("weak_mastery_threshold", 0.6, "float", "Ngưỡng 'điểm yếu'",
              "UC-86: mastery dưới ngưỡng thì từ được xếp vào nhóm cần ôn lại", 0.1, 0.9),
    ConfigDef("weak_session_size", 15, "int", "Số từ mỗi phiên ôn điểm yếu",
              "UC-86: số từ tối đa lấy vào một phiên ôn tập điểm yếu", 1, 100),
    ConfigDef("level_up_mastery_threshold", 0.85, "float", "Mastery trung bình để nâng trình độ",
              "BR-LU-02: mastery trung bình trên các từ thuộc mức hiện tại", 0.5, 1.0),
    ConfigDef("level_up_min_items", 20, "int", "Số từ tối thiểu để xét nâng trình độ",
              "BR-LU-02: chưa học đủ số từ này thì chưa đủ căn cứ để đề xuất", 1, 500),
    ConfigDef("matching_round_size", 5, "int", "Số cặp mỗi lượt ghép cặp",
              "UC-28: số từ hiển thị trong một lượt bài ghép cặp", 2, 12),
    ConfigDef("challenge_answer_target", 20, "int", "Thử thách: số từ trả lời/ngày",
              "UC-44: mục tiêu thử thách 'trả lời N từ'", 1, 500),
    ConfigDef("challenge_answer_xp", 20, "int", "Thử thách: XP thưởng khi trả lời đủ",
              "UC-44: XP nhận khi hoàn thành thử thách trả lời", 1, 500),
    ConfigDef("challenge_correct_target", 15, "int", "Thử thách: số từ trả lời ĐÚNG/ngày",
              "UC-44: mục tiêu thử thách 'trả lời đúng N từ'", 1, 500),
    ConfigDef("challenge_correct_xp", 30, "int", "Thử thách: XP thưởng khi đúng đủ",
              "UC-44: XP nhận khi hoàn thành thử thách trả lời đúng", 1, 500),
    ConfigDef("challenge_session_target", 1, "int", "Thử thách: số phiên hoàn thành/ngày",
              "UC-44: mục tiêu thử thách 'hoàn thành N phiên'", 1, 20),
    ConfigDef("challenge_session_xp", 15, "int", "Thử thách: XP thưởng khi đủ phiên",
              "UC-44: XP nhận khi hoàn thành thử thách phiên học", 1, 500),
    ConfigDef("pdf_import_max_mb", 10, "int", "PDF: dung lượng tối đa (MB)",
              "UC-87/BR-PDF-04: file lớn hơn mức này bị từ chối", 1, 100),
    ConfigDef("pdf_import_max_pages", 50, "int", "PDF: số trang tối đa",
              "UC-87/BR-PDF-04: tài liệu dài hơn mức này bị từ chối", 1, 500),
    ConfigDef("pdf_import_max_words", 500, "int", "PDF: số từ ứng viên tối đa",
              "UC-87: giữ lại N từ xuất hiện nhiều nhất để bảng duyệt còn dùng được", 20, 5000),
    # ---- Pilot kiểm chứng DKT trên người dùng thật ----
    ConfigDef("explore_rate", 0.15, "float", "Tỉ lệ từ thăm dò ngẫu nhiên",
              "Pilot: phần từ trong mỗi phiên 'Học thông minh' chọn ngẫu nhiên thay vì "
              "theo vùng vừa sức, để đo độ chính xác của DKT trên toàn dải 0–1 mà không "
              "bị thiên lệch chọn mẫu. 0 = tắt", 0.0, 0.5),
    ConfigDef("alternate_card_quiz", True, "bool", "Luân phiên thẻ lật / trắc nghiệm",
              "Pilot: ở 'Học thông minh' và 'Ôn tập', từ lần trước làm trắc nghiệm thì lần "
              "này là thẻ lật và ngược lại, cho đa dạng. Tắt = từ đủ điều kiện luôn ra "
              "trắc nghiệm (chấm khách quan 100%)", None, None),
    ConfigDef("validation_open", False, "bool", "Mở bài kiểm tra cuối",
              "Pilot: bật vào ngày cuối để người học làm bài kiểm tra độc lập "
              "(gõ từ, không gợi ý, không đổi lịch ôn)", None, None),
    ConfigDef("validation_size", 30, "int", "Số từ trong bài kiểm tra cuối",
              "Pilot: lấy đều theo 5 khoảng mastery", 10, 100),
    ConfigDef("shadowing_pass_accuracy", 0.8, "float", "Shadowing: độ chính xác để câu đạt",
              "UC-97: tỉ lệ từ nhại đúng tối thiểu để tính một câu là đã đạt", 0.5, 1.0),
]
_BY_KEY = {c.key: c for c in CONFIG_DEFS}

_cache: dict[str, str] | None = None


def reset_cache() -> None:
    """Buộc nạp lại từ DB ở lần đọc kế tiếp (dùng trong test & sau khi lưu)."""
    global _cache
    _cache = None


def _ensure_loaded() -> dict[str, str]:
    global _cache
    if _cache is None:
        from app.core.database import SessionLocal

        with SessionLocal() as db:
            _cache = {
                row.key: row.value
                for row in db.execute(select(SystemConfig)).scalars().all()
            }
    return _cache


def _parse(definition: ConfigDef, raw: str) -> float | int | bool:
    if definition.value_type == "bool":
        return raw.lower() in {"1", "true", "yes"}
    if definition.value_type == "int":
        return int(float(raw))
    return float(raw)


def get(key: str) -> float | int | bool:
    """Giá trị hiện tại của tham số (mặc định nếu Admin chưa chỉnh)."""
    definition = _BY_KEY[key]
    raw = _ensure_loaded().get(key)
    if raw is None:
        return definition.default
    try:
        return _parse(definition, raw)
    except ValueError:
        return definition.default


def get_float(key: str) -> float:
    return float(get(key))


def get_int(key: str) -> int:
    return int(get(key))


def get_bool(key: str) -> bool:
    return bool(get(key))


def list_configs() -> list[dict]:
    """UC-81 bước 1 — tham số hiện tại kèm mô tả & khoảng an toàn."""
    return [
        {
            "key": c.key, "value": get(c.key), "value_type": c.value_type,
            "label": c.label, "description": c.description,
            "minimum": c.minimum, "maximum": c.maximum,
            "default": c.default,
        }
        for c in CONFIG_DEFS
    ]


def _validate(definition: ConfigDef, value: float | int | bool) -> str:
    """E1 — giá trị ngoài khoảng an toàn thì chặn."""
    if definition.value_type == "bool":
        return "true" if bool(value) else "false"

    number = float(value)
    if definition.minimum is not None and number < definition.minimum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{definition.label}: giá trị tối thiểu là {definition.minimum}",
        )
    if definition.maximum is not None and number > definition.maximum:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{definition.label}: giá trị tối đa là {definition.maximum}",
        )
    return str(int(number)) if definition.value_type == "int" else str(number)


def set_values(db: Session, updates: dict[str, float | int | bool]) -> list[str]:
    """UC-81 bước 2 — lưu tham số & áp dụng ngay. Trả mô tả các thay đổi (cho audit)."""
    unknown = set(updates) - set(_BY_KEY)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tham số không hợp lệ: {', '.join(sorted(unknown))}",
        )

    # Kiểm tra từng giá trị TRƯỚC khi ghi (E1) để không lưu nửa vời
    validated = {key: _validate(_BY_KEY[key], value) for key, value in updates.items()}

    # Ràng buộc chéo: vùng vừa sức phải hợp lệ (BR-03)
    band_low = float(validated.get("band_low", get_float("band_low")))
    band_high = float(validated.get("band_high", get_float("band_high")))
    if band_low >= band_high:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cận dưới vùng vừa sức phải nhỏ hơn cận trên",
        )

    cache = _ensure_loaded()
    changes: list[str] = []
    for key, value in validated.items():
        old = get(key)
        row = db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        ).scalar_one_or_none()
        if row is None:
            db.add(SystemConfig(key=key, value=value))
        else:
            row.value = value

        cache[key] = value
        new = get(key)
        if old != new:
            changes.append(f"{key}: {old} -> {new}")

    db.commit()
    return changes
