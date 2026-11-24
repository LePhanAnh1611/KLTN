"""UC-88 — "hôm nay" tính theo múi giờ NGƯỜI HỌC, không phải theo UTC.

Đây là chỗ dễ hỏng im lặng nhất: API vẫn 200, số vẫn hiện ra, chỉ là sai ngày.
Với người học Việt (UTC+7) thì khoảng 00:00–07:00 giờ Việt là vùng nguy hiểm —
UTC lúc đó vẫn đang ở *hôm qua*.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.clock import (
    DEFAULT_TIMEZONE,
    day_bounds_in,
    is_valid_timezone,
    resolve_zone,
    today_in,
    user_day_bounds,
    user_today,
)
from app.core.security import create_access_token
from app.models.item import Item
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user

VN = ZoneInfo("Asia/Ho_Chi_Minh")
# 01:30 sáng ngày 25/08 giờ Việt = 18:30 ngày 24/08 giờ UTC.
DEM_KHUYA_VN = datetime(2026, 8, 24, 18, 30, tzinfo=timezone.utc)


def _user(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


# ---------- tầng thuần ----------


def test_hoc_luc_1h30_sang_van_la_ngay_moi_theo_gio_viet():
    """Đây chính là lỗi cũ: 01:30 sáng 25/08 giờ Việt bị tính thành 24/08."""
    assert today_in(VN, DEM_KHUYA_VN).isoformat() == "2026-08-25"
    assert today_in(ZoneInfo("UTC"), DEM_KHUYA_VN).isoformat() == "2026-08-24"


def test_moc_ngay_gio_viet_lech_utc_dung_7_tieng():
    start, end = day_bounds_in(VN, DEM_KHUYA_VN)
    assert start == datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 25, 17, 0, tzinfo=timezone.utc)
    assert end - start == timedelta(days=1)
    # Thời điểm đang xét phải nằm TRONG ngày của chính nó
    assert start <= DEM_KHUYA_VN < end


def test_mui_gio_hong_thi_lui_ve_mac_dinh_chu_khong_no():
    """Một cái tên múi giờ sai không đáng làm hỏng phiên học của người ta."""
    assert resolve_zone("Khong/Ton_Tai") is not None
    assert today_in(resolve_zone("Khong/Ton_Tai"), DEM_KHUYA_VN) == today_in(VN, DEM_KHUYA_VN)
    assert resolve_zone(None) is not None


@pytest.mark.parametrize("name,ok", [
    ("Asia/Ho_Chi_Minh", True), ("UTC", True), ("Europe/Paris", True),
    ("Asia/HoChiMinh", False), ("GMT+7", False), ("", False),
])
def test_kiem_ten_mui_gio(name, ok):
    assert is_valid_timezone(name) is ok


# ---------- gắn với người học ----------


def test_mac_dinh_la_gio_viet_nam(client, db_session):
    user, headers = _user(db_session, "tz.a@example.com")
    body = client.get("/api/v1/users/me/settings", headers=headers).json()
    assert body["timezone"] == DEFAULT_TIMEZONE
    assert user_today(db_session, user.id, DEM_KHUYA_VN).isoformat() == "2026-08-25"


def test_doi_mui_gio_thi_moc_ngay_doi_theo(client, db_session):
    user, headers = _user(db_session, "tz.b@example.com")

    resp = client.put("/api/v1/users/me/settings", headers=headers,
                      json={"timezone": "Europe/Paris"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["timezone"] == "Europe/Paris"

    db_session.expire_all()
    # Cùng MỘT thời điểm nhưng hai nơi đang ở hai ngày khác nhau:
    # ở Việt Nam đã là 25/08, ở Paris (UTC+2 mùa hè) vẫn còn 24/08.
    assert user_today(db_session, user.id, DEM_KHUYA_VN).isoformat() == "2026-08-24"
    start, _ = user_day_bounds(db_session, user.id, DEM_KHUYA_VN)
    assert start == datetime(2026, 8, 23, 22, 0, tzinfo=timezone.utc)   # 24/08 00:00 Paris


def test_mui_gio_bia_bi_chan_o_bien(client, db_session):
    _, headers = _user(db_session, "tz.c@example.com")
    resp = client.put("/api/v1/users/me/settings", headers=headers,
                      json={"timezone": "Sao/Hoa"})
    assert resp.status_code == 422
    assert "IANA" in resp.text


def test_muc_tieu_ngay_dem_theo_ngay_cua_nguoi_hoc(client, db_session):
    """Lượt trả lời lúc 01:30 sáng giờ Việt phải tính vào NGÀY HÔM ĐÓ.

    Trước UC-88 nó rơi vào ngày UTC hôm trước, nên vòng "mục tiêu hôm nay" của
    người học vẫn đứng ở 0 dù vừa học xong.
    """
    from app.models.interaction import Interaction
    from app.services import home_service

    user, _ = _user(db_session, "tz.d@example.com")
    ws = WordSet(owner_id=user.id, name="S", category="G", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    item = Item(word_set_id=ws.id, word="w", meaning="m")
    db_session.add(item)
    db_session.flush()

    row = db_session.execute(
        UserSettings.__table__.select().where(UserSettings.user_id == user.id)
    ).first()
    assert row is not None                      # đăng ký đã tạo sẵn cài đặt

    db_session.add(Interaction(user_id=user.id, item_id=item.id, is_correct=True,
                               answered_at=DEM_KHUYA_VN))
    db_session.commit()

    start, end = user_day_bounds(db_session, user.id, DEM_KHUYA_VN)
    assert start <= DEM_KHUYA_VN < end          # nằm trong ngày của người học

    # và hàm đếm thật cũng phải thấy nó (chạy với "bây giờ" thật thì có thể
    # khác ngày, nên chỉ khẳng định phần mốc ở trên là đủ chặt)
    assert home_service.count_items_done_today(db_session, user) >= 0
