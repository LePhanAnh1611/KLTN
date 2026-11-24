"""Pilot — báo cáo theo dõi đợt thử nghiệm với người dùng thật."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class PilotCriterion(BaseModel):
    """Một điều kiện 'đủ dữ liệu để calibrate'."""

    key: str
    label: str
    why: str          # vì sao cần — viết cho người không chuyên đọc
    current: int
    target: int
    met: bool


class PilotParticipant(BaseModel):
    user_id: int
    display_name: str
    email: str
    registered_at: datetime
    placement_done: bool
    active_days: int
    answers_total: int
    answers_today: int
    last_active_at: datetime | None
    #: số ngày (theo giờ pilot) kể từ lần học gần nhất; None = chưa học lần nào
    days_inactive: int | None
    needs_nudge: bool
    validation_done: bool


class PilotBin(BaseModel):
    low: float
    high: float
    count: int
    #: tỉ lệ trả lời đúng THỰC TẾ trong khoảng — xem nhanh độ hiệu chuẩn
    accuracy: float | None


class PilotReport(BaseModel):
    generated_at: datetime
    pilot_start: date | None
    pilot_day: int | None              # hôm nay là ngày thứ mấy của pilot
    registered: int                    # người học đã đăng ký
    participants: int                  # đã trả lời ít nhất 1 câu
    active_today: int
    answers_today: int
    answers_total: int
    model_share: float | None          # tỉ lệ lượt có dự đoán của DKT (thấp = ml-serve có vấn đề)
    explore_answers: int
    validation_done: int
    criteria: list[PilotCriterion]
    ready: bool                        # mọi điều kiện đều đạt
    bins: list[PilotBin]
    people: list[PilotParticipant]
