"""UC-89 — bài gõ từ (nhớ chủ động).

Vì sao cần dạng bài này khi đã có trắc nghiệm và điền khuyết:

* Trắc nghiệm/ghép cặp là **nhận diện** — đáp án bày sẵn, chỉ cần nhận ra.
* Điền khuyết có gõ, nhưng đòi câu ví dụ *chứa chính từ đó*; bộ từ nhập tay
  thường không có nên `generate_cloze` trả 400.
* Gõ từ chỉ cần `word` + `meaning`, tức chạy được trên **mọi** bộ từ, và buộc
  người học lôi từ trong đầu ra thay vì nhận mặt.
"""
from __future__ import annotations

from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _setup(db_session, email: str, *, with_example: bool = False, n: int = 5):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name="U"),
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    ws = WordSet(owner_id=user.id, name="Bộ gõ", category="Gen", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [
        Item(
            word_set_id=ws.id, word=f"word{i}", meaning=f"nghĩa {i}",
            part_of_speech="noun",
            example=(f"This is word{i} in a sentence." if with_example else None),
        )
        for i in range(n)
    ]
    db_session.add_all(items)
    db_session.commit()
    return user, headers, ws, items


def test_sinh_duoc_bai_go_tu(client, db_session):
    _, headers, ws, _ = _setup(db_session, "ty.a@example.com")

    resp = client.get(f"/api/v1/word-sets/{ws.id}/typing?limit=3", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 3

    q = body[0]
    assert q["meaning"].startswith("nghĩa")          # đề bài là NGHĨA
    assert q["answer"].startswith("word")            # đáp án là TỪ
    assert q["first_letter"] == q["answer"][0]
    assert q["length"] == len(q["answer"])
    assert q["part_of_speech"] == "noun"


def test_chay_duoc_tren_bo_tu_KHONG_co_cau_vi_du(client, db_session):
    """Đây là lý do tồn tại của UC-89: điền khuyết chết ở đúng chỗ này."""
    _, headers, ws, _ = _setup(db_session, "ty.b@example.com", with_example=False)

    cloze = client.get(f"/api/v1/word-sets/{ws.id}/cloze", headers=headers)
    assert cloze.status_code == 400                  # không có câu ví dụ -> chịu

    typing = client.get(f"/api/v1/word-sets/{ws.id}/typing", headers=headers)
    assert typing.status_code == 200 and len(typing.json()) == 5


def test_bo_tu_rong_thi_400(client, db_session):
    _, headers, ws, _ = _setup(db_session, "ty.c@example.com", n=0)
    resp = client.get(f"/api/v1/word-sets/{ws.id}/typing", headers=headers)
    assert resp.status_code == 400
    assert "gõ từ" in resp.json()["detail"]


def test_bo_qua_tu_khong_co_nghia(client, db_session):
    """Từ cắt từ PDF (UC-87) có thể chưa có nghĩa — không thể làm đề bài."""
    _, headers, ws, items = _setup(db_session, "ty.d@example.com", n=3)
    items[0].meaning = ""
    db_session.commit()

    body = client.get(f"/api/v1/word-sets/{ws.id}/typing", headers=headers).json()
    assert len(body) == 2
    assert all(q["meaning"].strip() for q in body)


def test_khong_dang_nhap_thi_401(client, db_session):
    _, _, ws, _ = _setup(db_session, "ty.e@example.com")
    assert client.get(f"/api/v1/word-sets/{ws.id}/typing").status_code == 401


def test_khong_lay_duoc_bo_tu_cua_nguoi_khac(client, db_session):
    _, _, ws, _ = _setup(db_session, "ty.f@example.com")
    _, other_headers, _, _ = _setup(db_session, "ty.g@example.com")
    resp = client.get(f"/api/v1/word-sets/{ws.id}/typing", headers=other_headers)
    assert resp.status_code == 404


def test_phien_hoc_che_do_go_tu_ghi_interaction(client, db_session, monkeypatch):
    """BR-05 — dạng bài mới vẫn phải ghi Interaction như mọi dạng khác."""
    from app.models.interaction import Interaction
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda h, t, **kwargs: {x: 0.7 for x in t})
    user, headers, ws, items = _setup(db_session, "ty.h@example.com")

    sid = client.post("/api/v1/sessions", headers=headers,
                      json={"word_set_id": ws.id, "mode": "typing"}).json()["id"]
    for item in items[:3]:
        resp = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                           json={"item_id": item.id, "is_correct": True,
                                 "answer": item.word,
                                 "response_time_ms": 4200})
        assert resp.status_code in (200, 204), resp.text
    summary = client.post(f"/api/v1/sessions/{sid}/complete", headers=headers).json()

    assert summary["total_answered"] == 3
    rows = db_session.query(Interaction).filter(Interaction.user_id == user.id).all()
    assert len(rows) == 3
    # Dạng bài được ghi lại — đây là thứ sau này cho phép đưa "loại bài tập" vào
    # đặc trưng của DKT (nhận diện dễ hơn nhớ chủ động).
    assert {r.exercise_format for r in rows} == {"typing"}


# ---------- UC-90 nghe viết · UC-91 phiên trộn ----------


def test_che_do_nghe_viet_va_phien_tron_mo_duoc_phien(client, db_session, monkeypatch):
    """Hai chế độ mới phải mở được phiên và ghi đúng `exercise_format`.

    Nghe viết dùng CHUNG endpoint /typing với gõ từ (payload y hệt, chỉ khác cách
    trình bày), nên chỗ cần kiểm là chế độ phiên chứ không phải endpoint mới.
    """
    from app.models.interaction import Interaction
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda h, t, **kwargs: {x: 0.7 for x in t})
    user, headers, ws, items = _setup(db_session, "ty.i@example.com", n=6)

    for mode in ("dictation", "mixed"):
        sid = client.post("/api/v1/sessions", headers=headers,
                          json={"word_set_id": ws.id, "mode": mode}).json()["id"]
        resp = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                           json={"item_id": items[0].id, "is_correct": True,
                                 "answer": items[0].word,
                                 "exercise_format": "typing" if mode == "mixed" else mode})
        assert resp.status_code in (200, 204), resp.text
        assert client.post(f"/api/v1/sessions/{sid}/complete",
                           headers=headers).status_code == 200

    formats = {
        r.exercise_format
        for r in db_session.query(Interaction).filter(Interaction.user_id == user.id).all()
    }
    assert {"dictation", "typing"} <= formats


def test_che_do_khong_hop_le_bi_chan(client, db_session):
    """Danh sách chế độ là whitelist — gõ bừa phải bị chặn ở schema."""
    _, headers, ws, _ = _setup(db_session, "ty.j@example.com")
    resp = client.post("/api/v1/sessions", headers=headers,
                       json={"word_set_id": ws.id, "mode": "khong_ton_tai"})
    assert resp.status_code == 422
