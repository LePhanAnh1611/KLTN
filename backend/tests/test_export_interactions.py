"""UC-71 bước 1 — xuất INTERACTION sang định dạng huấn luyện.

Điểm cần canh không phải "chạy được" mà là **chia tập theo THỜI GIAN**: chia
ngẫu nhiên sẽ để lượt trả lời sau rơi vào tập train và lượt trước rơi vào test,
tức rò rỉ tương lai vào quá khứ — đúng lỗi mà tiền xử lý SLAM đã tránh.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.scripts.export_interactions import (
    FORMAT_OTHER,
    collect,
    format_code,
    report,
    split_of,
)
from app.services.auth_service import register_user


def _seed(db_session, email: str, n: int = 10):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    ws = WordSet(owner_id=user.id, name="S", category="G", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"w{i}", meaning=f"m{i}") for i in range(n)]
    db_session.add_all(items)
    db_session.flush()

    base = datetime.now(timezone.utc) - timedelta(days=1)
    modes = ["quiz", "typing", "dictation"]
    for i, item in enumerate(items):
        db_session.add(Interaction(
            user_id=user.id, item_id=item.id, is_correct=(i % 2 == 0),
            exercise_format=modes[i % len(modes)],
            answered_at=base + timedelta(minutes=i),
        ))
    db_session.commit()
    return user, items


def test_ma_dang_bai_quy_ve_ba_nhom_cua_slam():
    assert format_code("quiz") == 0 and format_code("matching") == 0
    assert format_code("typing") == 1 and format_code("cloze") == 1
    assert format_code("dictation") == 2
    # "mixed" gồm nhiều dạng -> không gán bừa một dạng nào
    assert format_code("mixed") == FORMAT_OTHER
    assert format_code(None) == FORMAT_OTHER


def test_chia_tap_theo_thu_tu_thoi_gian():
    """70% đầu -> train, 15% giữa -> dev, phần cuối -> test. Không xáo trộn."""
    splits = [split_of(i, 20) for i in range(20)]
    assert splits[:14] == ["train"] * 14
    assert splits[14:17] == ["dev"] * 3
    assert splits[17:] == ["test"] * 3
    # ranh giới phải đơn điệu: không có 'train' nào nằm sau 'test'
    order = {"train": 0, "dev": 1, "test": 2}
    assert all(order[a] <= order[b] for a, b in zip(splits, splits[1:]))


def test_thu_thap_giu_dung_thu_tu_va_dang_bai(db_session):
    user, items = _seed(db_session, "ex.a@example.com", n=6)
    seqs = collect(db_session)

    seq = seqs[user.id]
    assert [w for w, _, _ in seq] == [it.word for it in items]      # đúng thứ tự thời gian
    assert [c for _, c, _ in seq] == [1, 0, 1, 0, 1, 0]
    assert [f for _, _, f in seq] == [0, 1, 2, 0, 1, 2]             # quiz/typing/dictation


def test_bao_cao_noi_KHONG_du_khi_du_lieu_it(db_session, capsys):
    """Đây là hành vi quan trọng nhất của script: biết từ chối."""
    _seed(db_session, "ex.b@example.com", n=5)
    ready = report(collect(db_session))
    assert ready is False
    assert "CHƯA ĐỦ" in capsys.readouterr().out
