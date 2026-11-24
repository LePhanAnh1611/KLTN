"""UC-39 — hội thoại roleplay với nhân vật AI.

Ba nhóm điểm cần canh:

1. **Độc lập với lõi DKT** (CLAUDE.md mục 7). Nói chuyện cả buổi không được sinh
   một INTERACTION nào — một câu nói không phải một lượt trả lời về một từ cụ
   thể, đưa vào DKT là làm bẩn đúng thứ đề tài đang đo.
2. **Ollama chết thì không để lại hội thoại lệch vai.** Ghi một mình lượt người
   học rồi mới gọi LLM là sai: lần sau mở lên thấy mình nói hai câu liền mà nhân
   vật im lặng.
3. **Mở được kể cả khi Ollama chưa chạy** — câu chào là văn bản cố định.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.conversation import Conversation, ConversationTurn
from app.models.interaction import Interaction
from app.schemas.auth import RegisterRequest
from app.services import conversation_service
from app.services.auth_service import register_user
from app.speaking.scoring.ollama_client import OllamaUnavailable


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


@pytest.fixture
def fake_llm(monkeypatch):
    """Thay Ollama bằng bản giả — test không được phụ thuộc máy có chạy LLM."""
    calls = []

    def _chat(system, user, **kwargs):
        calls.append({"system": system, "user": user})
        return {"reply": "Sure, one flat white coming up. Anything else?",
                "correction": "I would like a coffee, please."}

    monkeypatch.setattr(conversation_service.ollama_client, "chat_json", _chat)
    return calls


# --- 1. Mở phiên ---------------------------------------------------------------

def test_danh_sach_kich_ban(client, db_session):
    _, headers = _user(db_session, "cv.a@example.com")
    rows = client.get("/api/v1/conversations/scenarios", headers=headers).json()
    assert {r["key"] for r in rows} == {"cafe", "airport", "interview", "smalltalk"}
    assert all(r["opening"] and r["persona"] and r["cefr"] for r in rows)
    # Bug #11: giọng đọc phải khớp giới tính nhân vật
    voices = {r["key"]: r["voice"] for r in rows}
    assert voices["cafe"] == "female"        # Emma
    assert voices["interview"] == "female"   # Ms. Clark
    assert voices["airport"] == "male"       # David


def test_mo_phien_duoc_ke_ca_khi_ollama_chet(client, db_session, monkeypatch):
    """Câu chào cố định nên không phụ thuộc LLM."""
    def _boom(*a, **k):
        raise OllamaUnavailable("khong co ollama")
    monkeypatch.setattr(conversation_service.ollama_client, "chat_json", _boom)

    _, headers = _user(db_session, "cv.b@example.com")
    body = client.post("/api/v1/conversations", headers=headers,
                       json={"scenario": "cafe"}).json()
    assert body["status"] == "active"
    assert len(body["turns"]) == 1
    assert body["turns"][0]["speaker"] == "ai"
    assert "Welcome in" in body["turns"][0]["text"]


def test_kich_ban_khong_ton_tai_thi_404(client, db_session):
    _, headers = _user(db_session, "cv.c@example.com")
    assert client.post("/api/v1/conversations", headers=headers,
                       json={"scenario": "khong-co"}).status_code == 404


# --- 2. Vòng hội thoại ---------------------------------------------------------

def test_tra_loi_ghi_du_hai_luot_dung_thu_tu(client, db_session, fake_llm):
    _, headers = _user(db_session, "cv.d@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]

    body = client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "I want a coffee"}).json()

    speakers = [t["speaker"] for t in body["turns"]]
    assert speakers == ["ai", "user", "ai"]
    assert [t["ordinal"] for t in body["turns"]] == [0, 1, 2]
    assert body["turns"][1]["correction"] == "I would like a coffee, please."


def test_prompt_co_lich_su_va_giu_vai(client, db_session, fake_llm):
    """Không đưa lịch sử vào thì nhân vật trả lời như chưa từng nói gì."""
    _, headers = _user(db_session, "cv.e@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "interview"}).json()["id"]
    client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                json={"text": "My name is An"})

    sent = fake_llm[-1]
    assert "Ms. Clark" in sent["user"]
    assert "tell me a little about yourself" in sent["user"]  # câu chào nằm trong lịch sử
    assert "My name is An" in sent["user"]
    assert "B2" in sent["system"]
    assert "JSON" in sent["system"]


def test_sua_cau_ma_chep_lai_y_nguyen_thi_bo(client, db_session, monkeypatch):
    """Model nhỏ hay 'sửa' bằng cách lặp lại câu — đó không phải sửa."""
    monkeypatch.setattr(
        conversation_service.ollama_client, "chat_json",
        lambda s, u, **k: {"reply": "Nice!", "correction": "I like coffee"},
    )
    _, headers = _user(db_session, "cv.f@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]
    body = client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "I like coffee"}).json()
    assert body["turns"][1]["correction"] is None


def test_ollama_chet_thi_503_va_KHONG_ghi_luot_nao(client, db_session, monkeypatch):
    _, headers = _user(db_session, "cv.g@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]

    def _boom(*a, **k):
        raise OllamaUnavailable("tat roi")
    monkeypatch.setattr(conversation_service.ollama_client, "chat_json", _boom)

    resp = client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "Hello there"})
    assert resp.status_code == 503

    turns = db_session.execute(
        select(func.count()).select_from(ConversationTurn)
        .where(ConversationTurn.conversation_id == cid)
    ).scalar_one()
    assert turns == 1, "chỉ còn câu chào — không được để lại lượt người học lơ lửng"


def test_llm_tra_loi_rong_thi_502(client, db_session, monkeypatch):
    monkeypatch.setattr(
        conversation_service.ollama_client, "chat_json",
        lambda s, u, **k: {"reply": "   ", "correction": None},
    )
    _, headers = _user(db_session, "cv.h@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]
    assert client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "Hi"}).status_code == 502


# --- 3. Ranh giới với lõi DKT ---------------------------------------------------

def test_khong_sinh_interaction_nao(client, db_session, fake_llm):
    """CLAUDE.md mục 7: module luyện nói độc lập với DKT."""
    user, headers = _user(db_session, "cv.i@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "smalltalk"}).json()["id"]
    for text in ("Hi Alex", "Yes it is", "I like reading"):
        client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                    json={"text": text})

    count = db_session.execute(
        select(func.count()).select_from(Interaction)
        .where(Interaction.user_id == user.id)
    ).scalar_one()
    assert count == 0


# --- 4. Vòng đời & phân quyền ----------------------------------------------------

def test_ket_thuc_roi_thi_khong_gui_them(client, db_session, fake_llm):
    _, headers = _user(db_session, "cv.j@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]
    ended = client.post(f"/api/v1/conversations/{cid}/end", headers=headers).json()
    assert ended["status"] == "ended" and ended["ended_at"]

    assert client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "Hello"}).status_code == 400


def test_cham_tran_so_luot(client, db_session, fake_llm, monkeypatch):
    monkeypatch.setattr(conversation_service, "MAX_TURNS", 3)
    _, headers = _user(db_session, "cv.k@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]
    client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                json={"text": "One"})          # -> 3 lượt
    assert client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "Two"}).status_code == 409


def test_khong_xem_duoc_hoi_thoai_cua_nguoi_khac(client, db_session, fake_llm):
    _, mine = _user(db_session, "cv.l@example.com")
    _, other = _user(db_session, "cv.m@example.com")
    cid = client.post("/api/v1/conversations", headers=mine,
                      json={"scenario": "cafe"}).json()["id"]

    assert client.get(f"/api/v1/conversations/{cid}", headers=other).status_code == 404
    assert client.post(f"/api/v1/conversations/{cid}/turns", headers=other,
                       json={"text": "Hi"}).status_code == 404


def test_lich_su_hoi_thoai(client, db_session, fake_llm):
    _, headers = _user(db_session, "cv.n@example.com")
    for scenario in ("cafe", "airport"):
        client.post("/api/v1/conversations", headers=headers, json={"scenario": scenario})

    rows = client.get("/api/v1/conversations", headers=headers).json()
    assert len(rows) == 2
    assert rows[0]["scenario"] == "airport", "mới nhất lên đầu"
    assert all(r["turn_count"] == 1 for r in rows)


def test_gui_chuoi_rong_thi_422(client, db_session, fake_llm):
    _, headers = _user(db_session, "cv.o@example.com")
    cid = client.post("/api/v1/conversations", headers=headers,
                      json={"scenario": "cafe"}).json()["id"]
    assert client.post(f"/api/v1/conversations/{cid}/turns", headers=headers,
                       json={"text": "   "}).status_code in (400, 422)


def test_yeu_cau_dang_nhap(client):
    assert client.get("/api/v1/conversations/scenarios").status_code == 401


def test_khong_luu_audio_cua_nguoi_hoc(client, db_session):
    """Bảng lượt chỉ có văn bản — không có cột nào giữ đường dẫn file ghi âm."""
    columns = {c.name for c in Conversation.__table__.columns}
    turn_columns = {c.name for c in ConversationTurn.__table__.columns}
    assert not any("audio_path" in c or "audio_url" in c for c in columns | turn_columns)
