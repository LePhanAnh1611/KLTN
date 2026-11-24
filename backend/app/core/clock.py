"""Ngày "hôm nay" theo múi giờ NGƯỜI HỌC, không phải theo UTC.

Vì sao cần cả một module cho việc này: streak (UC-47), mục tiêu ngày (UC-41),
thử thách ngày (UC-44) và trần XP (BR-XP-01) đều xoay quanh câu hỏi "hôm nay là
ngày nào". Trước đây mọi chỗ đều hỏi `datetime.now(timezone.utc).date()`, nghĩa
là với người học Việt Nam (UTC+7) thì **từ 00:00 đến 07:00 giờ Việt, hệ thống
vẫn tính là hôm qua**: học lúc 1 giờ sáng thì streak không nhích, thử thách chưa
reset, XP cộng nhầm ngày.

Quy ước:
* Múi giờ lưu ở `USER_SETTINGS.timezone` dạng tên IANA (VD `Asia/Ho_Chi_Minh`).
* Mọi mốc trả về đều là datetime **aware theo UTC** để so trực tiếp với các cột
  `TIMESTAMPTZ` trong DB — chuyển múi giờ chỉ để *xác định ranh giới ngày*, còn
  truy vấn vẫn chạy trên trục UTC.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_settings import UserSettings

#: Sản phẩm phục vụ người học Việt Nam nên mặc định là giờ Việt Nam, không phải UTC.
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"


def resolve_zone(name: str | None) -> ZoneInfo:
    """Đổi tên IANA thành ZoneInfo; tên hỏng thì lùi về mặc định thay vì nổ.

    Một cái tên múi giờ sai không đáng làm hỏng phiên học của người ta.
    """
    for candidate in (name, DEFAULT_TIMEZONE):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def user_zone(db: Session, user_id: int) -> ZoneInfo:
    """Múi giờ của người học (mặc định giờ Việt Nam khi chưa đặt)."""
    name = db.execute(
        select(UserSettings.timezone).where(UserSettings.user_id == user_id)
    ).scalar_one_or_none()
    return resolve_zone(name)


def today_in(zone: ZoneInfo, moment: datetime | None = None) -> date:
    """Ngày lịch hiện tại NHÌN TỪ múi giờ đó."""
    now = moment or datetime.now(timezone.utc)
    return now.astimezone(zone).date()


def day_bounds_in(zone: ZoneInfo, moment: datetime | None = None) -> tuple[datetime, datetime]:
    """Mốc đầu/cuối của "hôm nay" theo `zone`, quy về UTC để truy vấn DB.

    VD Asia/Ho_Chi_Minh: ngày 25/08 chạy từ 24/08 17:00 UTC đến 25/08 17:00 UTC.
    """
    day = today_in(zone, moment)
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def user_today(db: Session, user_id: int, moment: datetime | None = None) -> date:
    return today_in(user_zone(db, user_id), moment)


def user_day_bounds(
    db: Session, user_id: int, moment: datetime | None = None
) -> tuple[datetime, datetime]:
    return day_bounds_in(user_zone(db, user_id), moment)
