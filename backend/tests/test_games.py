"""UC-94 — trò chơi từ vựng.

Điểm quan trọng nhất, và cũng là chỗ dễ hỏng âm thầm nhất: **dạng bài gửi cho
DKT**. Mô hình chỉ được huấn luyện trên một tập mã dạng bài hữu hạn; nếu phiên
trò chơi ghi 'game_rain' vào INTERACTION thì mã đó rơi vào "other" — chưa từng
được huấn luyện. API vẫn 200, mastery vẫn có số, chỉ là sai. Nên server tự suy
dạng bài từ chế độ phiên, không tin client.

Ngoài ra: trò chơi phải ghi INTERACTION đầy đủ (BR-05) như mọi dạng bài khác —
nếu không thì nó chỉ là đồ trang trí nằm ngoài mô hình.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import game_service
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _set(db_session, owner, n=6):
    ws = WordSet(owner_id=owner.id, name="Bộ chơi", category="G", difficulty="beginner")
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=f"word{i}", meaning=f"nghĩa {i}") for i in range(n)]
    db_session.add_all(items)
    db_session.commit()
    return ws, items


def _start(client, headers, ws_id, mode):
    return client.post("/api/v1/sessions", headers=headers,
                       json={"word_set_id": ws_id, "mode": mode}).json()["id"]


# --- 1. Dạng bài gửi cho mô hình ---------------------------------------------

def test_moi_tro_anh_xa_ve_mot_dang_bai_da_duoc_huan_luyen():
    """Ba trò không phải ba dạng bài mới — chúng là ba dạng đã có, mặc áo khác."""
    formats = {g.key: g.exercise_format for g in game_service.GAMES}
    assert formats == {"rain": "typing", "spelling": "dictation", "match": "matching"}


def test_server_tu_suy_dang_bai_khong_tin_client(client, db_session):
    """Client gửi bừa dạng bài thì server vẫn ghi đúng dạng của trò."""
    user, headers = _user(db_session, "gm.a@example.com")
    ws, items = _set(db_session, user)
    sid = _start(client, headers, ws.id, "game_rain")

    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[0].id, "is_correct": True,
        "answer": items[0].word,
        "exercise_format": "khong-ton-tai", "response_time_ms": 1200,
    })

    saved = db_session.execute(
        select(Interaction).where(Interaction.session_id == sid)
    ).scalars().all()
    assert len(saved) == 1
    assert saved[0].exercise_format == "typing", "phải là dạng bài của trò, không phải thứ client gửi"


def test_khong_gui_dang_bai_cung_khong_roi_ve_ma_game(client, db_session):
    """Bỏ trống dạng bài thì fallback cũ sẽ ghi 'game_spelling' — mã chưa huấn luyện."""
    user, headers = _user(db_session, "gm.b@example.com")
    ws, items = _set(db_session, user)
    sid = _start(client, headers, ws.id, "game_spelling")

    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
                json={"item_id": items[0].id, "is_correct": False, "answer": ""})

    row = db_session.execute(
        select(Interaction).where(Interaction.session_id == sid)
    ).scalar_one()
    assert row.exercise_format == "dictation"


def test_phien_thuong_van_ton_trong_dang_bai_client_gui(client, db_session):
    """Chốt chặn chỉ áp cho phiên trò chơi — phiên trộn (UC-91) vẫn cần client báo."""
    user, headers = _user(db_session, "gm.c@example.com")
    ws, items = _set(db_session, user)
    sid = _start(client, headers, ws.id, "mixed")

    client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
        "item_id": items[0].id, "is_correct": True, "exercise_format": "dictation",
        "answer": items[0].word,
    })
    row = db_session.execute(
        select(Interaction).where(Interaction.session_id == sid)
    ).scalar_one()
    assert row.exercise_format == "dictation"


# --- 2. BR-05: trò chơi vẫn nuôi mô hình --------------------------------------

def test_tro_choi_ghi_interaction_day_du(client, db_session):
    user, headers = _user(db_session, "gm.d@example.com")
    ws, items = _set(db_session, user)
    sid = _start(client, headers, ws.id, "game_match")

    for i, item in enumerate(items[:4]):
        client.post(f"/api/v1/sessions/{sid}/answer", headers=headers, json={
            "item_id": item.id, "is_correct": i % 2 == 0, "response_time_ms": 800 + i,
            "answer": item.meaning if i % 2 == 0 else "wrong",
        })

    rows = db_session.execute(
        select(Interaction).where(Interaction.session_id == sid)
        .order_by(Interaction.id)
    ).scalars().all()
    assert len(rows) == 4
    assert [r.is_correct for r in rows] == [True, False, True, False]
    assert [r.response_time_ms for r in rows] == [800, 801, 802, 803]
    assert {r.exercise_format for r in rows} == {"matching"}


# --- 3. Điểm & bảng xếp hạng ---------------------------------------------------

def test_danh_muc_tro_choi(client, db_session):
    _, headers = _user(db_session, "gm.e@example.com")
    body = client.get("/api/v1/games", headers=headers).json()
    assert {g["key"] for g in body} == {"rain", "spelling", "match"}
    assert all(g["best_score"] is None and g["plays"] == 0 for g in body)


def test_chi_nang_ky_luc_khi_diem_cao_hon(client, db_session):
    _, headers = _user(db_session, "gm.f@example.com")
    first = client.post("/api/v1/games/rain/scores", headers=headers,
                        json={"score": 500}).json()
    assert first["is_new_best"] is True and first["best_score"] == 500

    lower = client.post("/api/v1/games/rain/scores", headers=headers,
                        json={"score": 200}).json()
    assert lower["is_new_best"] is False
    assert lower["best_score"] == 500, "kỷ lục không được tụt"
    assert lower["plays"] == 2, "số ván vẫn tăng dù thua"

    higher = client.post("/api/v1/games/rain/scores", headers=headers,
                         json={"score": 900}).json()
    assert higher["is_new_best"] is True and higher["best_score"] == 900


def test_diem_bi_chan_tran(client, db_session):
    _, headers = _user(db_session, "gm.g@example.com")
    body = client.post("/api/v1/games/rain/scores", headers=headers,
                       json={"score": 10**9}).json()
    assert body["best_score"] == game_service.MAX_SCORE_PER_ROUND


def test_bang_xep_hang_sap_theo_diem_giam_dan(client, db_session):
    for i, score in enumerate([300, 900, 600]):
        _, headers = _user(db_session, f"gm.h{i}@example.com")
        client.post("/api/v1/games/match/scores", headers=headers, json={"score": score})

    _, viewer = _user(db_session, "gm.hv@example.com")
    rows = client.get("/api/v1/games/match/leaderboard", headers=viewer).json()
    assert [r["best_score"] for r in rows] == [900, 600, 300]
    assert [r["rank"] for r in rows] == [1, 2, 3]


def test_hang_cua_minh_dung_bang_so_nguoi_cao_hon_cong_mot(client, db_session):
    for i, score in enumerate([1000, 800]):
        _, h = _user(db_session, f"gm.i{i}@example.com")
        client.post("/api/v1/games/spelling/scores", headers=h, json={"score": score})

    _, headers = _user(db_session, "gm.iz@example.com")
    body = client.post("/api/v1/games/spelling/scores", headers=headers,
                       json={"score": 900}).json()
    assert body["rank"] == 2


def test_diem_0_khong_len_bang_xep_hang(client, db_session):
    _, headers = _user(db_session, "gm.j@example.com")
    client.post("/api/v1/games/rain/scores", headers=headers, json={"score": 0})
    rows = client.get("/api/v1/games/rain/leaderboard", headers=headers).json()
    assert rows == []


def test_tro_khong_ton_tai_thi_404(client, db_session):
    _, headers = _user(db_session, "gm.k@example.com")
    assert client.post("/api/v1/games/khong-co/scores", headers=headers,
                       json={"score": 10}).status_code == 404
    assert client.get("/api/v1/games/khong-co/leaderboard",
                      headers=headers).status_code == 404


def test_yeu_cau_dang_nhap(client):
    assert client.get("/api/v1/games").status_code == 401
