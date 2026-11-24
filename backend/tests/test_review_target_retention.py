"""UC-66 bản sửa — lập lịch nhắm mức nhớ mục tiêu.

Luật cũ tra mastery vào bảng bậc {1,2,4,7} ngày và thua SM-2 ở cả sáu kịch bản
mô phỏng (UC-93). Luật mới giữ ước lượng nửa đời rồi đặt lịch tại
`t = h · log2(1/mục_tiêu)`.

Điểm cần canh, theo thứ tự quan trọng:
1. Trả lời SAI phải kéo lịch lại gần, kể cả khi mastery vẫn còn cao — đây đúng là
   ca mà luật cũ hỏng.
2. Nửa đời phải được LƯU, nếu không thì mỗi lượt lại bắt đầu từ con số khởi tạo
   và toàn bộ ý tưởng giãn dần mất sạch.
3. Có sàn/trần: nửa đời về 0 làm lịch kẹt ở "ngay lập tức" vĩnh viễn.
"""
from __future__ import annotations

import math

import pytest

from app.models.review_schedule import ReviewSchedule
from app.schemas.auth import RegisterRequest
from app.services import review_service
from app.services.auth_service import register_user
from app.models.item import Item
from app.models.word_set import WordSet


def _user_item(db_session, email):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    ws = WordSet(owner_id=user.id, name="S", category="G", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    item = Item(word_set_id=ws.id, word="habitat", meaning="môi trường sống")
    db_session.add(item)
    db_session.commit()
    return user, item


def _schedule(db_session, user, item, mastery, correct):
    return review_service.schedule_review(
        db_session, user.id, item.id, mastery, is_correct=correct
    )


def test_khoang_cach_dat_dung_muc_nho_muc_tieu():
    """t = h·log2(1/mục tiêu): với mục tiêu 0,9 thì t ≈ 0,152·h."""
    target = review_service.target_retention()
    for h in (14.0, 40.0, 120.0):
        days = review_service.half_life_to_interval_days(h)
        assert 2 ** (-days / h) == pytest.approx(target, abs=0.03)


def test_nua_doi_ngan_thi_bi_san_1_ngay_chan_lai():
    """Không ôn được nhanh hơn một ngày, nên với h nhỏ mức nhớ sẽ THẤP hơn mục
    tiêu chứ không cao hơn — thà ôn sớm còn hơn để quên."""
    h = 2.0
    days = review_service.half_life_to_interval_days(h)
    assert days == 1
    assert 2 ** (-days / h) < review_service.target_retention()


def test_tra_loi_sai_keo_lich_lai_gan_du_mastery_van_cao(client, db_session):
    """Đây là ca luật cũ hỏng: mastery 0,92 -> luôn 7 ngày, bất kể vừa sai."""
    user, item = _user_item(db_session, "tr.a@example.com")
    for _ in range(5):                       # xây một chuỗi đúng để nửa đời dài ra
        rs = _schedule(db_session, user, item, 0.92, True)
    # `schedule_review` cập nhật TẠI CHỖ và trả về cùng một hàng ORM, nên phải
    # chụp lại giá trị chứ không giữ tham chiếu — giữ tham chiếu thì hai mốc so
    # sánh trỏ vào cùng một đối tượng và test luôn luôn xanh một cách vô nghĩa.
    interval_dung, h_dung = rs.interval_days, rs.half_life_days
    assert interval_dung > 7  # đã giãn vượt trần cứng của luật cũ

    rs = _schedule(db_session, user, item, 0.92, False)
    assert rs.interval_days < interval_dung
    assert rs.half_life_days < h_dung


def test_nua_doi_duoc_luu_va_gian_dan(client, db_session):
    user, item = _user_item(db_session, "tr.b@example.com")
    seen = []
    for _ in range(5):
        seen.append(float(_schedule(db_session, user, item, 0.85, True).half_life_days))
    assert seen == sorted(seen), "nửa đời phải tăng dần qua các lượt đúng"
    assert seen[-1] > seen[0] * 2

    stored = db_session.query(ReviewSchedule).filter_by(
        user_id=user.id, item_id=item.id
    ).one()
    assert stored.half_life_days == pytest.approx(seen[-1])


def test_tu_nam_chac_gian_nhanh_hon_tu_con_yeu(client, db_session):
    """DKT giữ đúng vai trò của nó: mastery điều biến tốc độ giãn."""
    u1, i1 = _user_item(db_session, "tr.c@example.com")
    u2, i2 = _user_item(db_session, "tr.d@example.com")
    for _ in range(3):
        chac = _schedule(db_session, u1, i1, 0.95, True)
        yeu = _schedule(db_session, u2, i2, 0.35, True)
    assert float(chac.half_life_days) > float(yeu.half_life_days)
    assert chac.interval_days > yeu.interval_days


def test_chuoi_sai_lien_tuc_khong_lam_nua_doi_ve_0(client, db_session):
    """Không có sàn thì lịch kẹt ở 'ngay lập tức' vĩnh viễn."""
    user, item = _user_item(db_session, "tr.e@example.com")
    for _ in range(30):
        rs = _schedule(db_session, user, item, 0.2, False)
    assert rs.half_life_days >= review_service.MIN_HALF_LIFE_DAYS
    assert rs.interval_days >= 1


def test_chuoi_dung_rat_dai_khong_day_lich_ra_vo_han(client, db_session):
    user, item = _user_item(db_session, "tr.f@example.com")
    for _ in range(60):
        rs = _schedule(db_session, user, item, 0.99, True)
    assert rs.half_life_days <= review_service.MAX_HALF_LIFE_DAYS
    assert rs.interval_days <= review_service.MAX_INTERVAL_DAYS


def test_khong_biet_ket_qua_thi_suy_tu_nguong_chu_khong_mac_dinh_dung(client, db_session):
    """`is_correct=None` với mastery thấp phải xử như một lượt sai."""
    user, item = _user_item(db_session, "tr.g@example.com")
    _schedule(db_session, user, item, 0.9, True)
    truoc = db_session.query(ReviewSchedule).filter_by(
        user_id=user.id, item_id=item.id
    ).one().half_life_days

    review_service.schedule_review(db_session, user.id, item.id, 0.2)  # dưới θ_review
    sau = db_session.query(ReviewSchedule).filter_by(
        user_id=user.id, item_id=item.id
    ).one().half_life_days
    assert sau < truoc


def test_luat_cu_van_con_nguyen_de_lam_moc_so_sanh():
    """UC-93 so với đúng hàm này; xóa nó là mất mốc của chương thực nghiệm."""
    assert review_service.mastery_to_interval_days(0.5) == 1
    assert review_service.mastery_to_interval_days(0.7) == 2
    assert review_service.mastery_to_interval_days(0.8) == 4
    assert review_service.mastery_to_interval_days(0.95) == 7
    assert math.isclose(review_service.target_retention(), 0.9, abs_tol=0.3)
