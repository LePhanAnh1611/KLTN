"""Bug #9 — chọn câu hỏi & đáp án nhiễu cho trắc nghiệm "chọn nghĩa đúng".

Phần thuần (không cần DB) chạy được riêng: `pytest --noconftest tests/test_quiz_distractors.py -k pure`.
"""
from app.models.item import Item
from app.services.quiz_service import meaning_is_quizzable, meanings_overlap, pick_distractors

from tests.test_sessions import _setup


# --- thuần -------------------------------------------------------------------

def test_pure_overlap_bat_cum_trung_va_long_nhau():
    assert meanings_overlap("đạo đức, luân thường đạo lý", "đạo đức học")      # lồng nhau
    assert meanings_overlap("chính, chủ yếu", "chủ yếu; quan trọng")          # trùng cụm
    assert not meanings_overlap("bánh mì", "bàn học")
    assert not meanings_overlap("nghia1", "nghia10")                         # không cắt giữa chữ


def test_pure_nghia_chua_tin_hoac_rac_khong_lam_cau_hoi():
    assert meaning_is_quizzable("bánh mì", "confirmed")
    assert meaning_is_quizzable("bánh mì", None)                 # người học tự nhập
    assert meaning_is_quizzable("bánh mì", "llm")
    assert not meaning_is_quizzable("vải chéo", "needs-review")
    assert not meaning_is_quizzable("xem abhorrent", "single-source")
    assert not meaning_is_quizzable("<Mỹ>", "single-source")
    assert not meaning_is_quizzable("  ", "confirmed")


def test_pure_nhieu_khong_trung_nghia_va_uu_tien_cung_tu_loai():
    pool = [
        ("đạo đức học", "noun", True),          # gần nghĩa đáp án -> loại
        ("bàn", "noun", True), ("ghế", "noun", True), ("cửa", "noun", True),
        ("chạy", "verb", True), ("nhảy", "verb", True),
        ("vải chéo", "noun", False),            # nghĩa chưa tin -> xếp cuối
    ]
    for _ in range(30):
        got = pick_distractors("đạo đức", "noun", pool)
        assert got is not None and len(got) == 3
        assert "đạo đức học" not in got
        assert set(got) == {"bàn", "ghế", "cửa"}      # cùng từ loại + đáng tin trước


def test_pure_khong_du_nhieu_hop_le_tra_none():
    assert pick_distractors("đạo đức", "noun", [("đạo đức học", "noun", True), ("bàn", "noun", True)]) is None


# --- API ---------------------------------------------------------------------

def test_quiz_bo_tu_nghia_needs_review_va_nhieu_trung_nghia(client, db_session):
    _, headers, ws, items = _setup(db_session, "quiz.bug9@example.com", n_items=5)
    flagged = Item(word_set_id=ws.id, word="say", meaning="vải chéo", meaning_confidence="needs-review")
    twin = Item(word_set_id=ws.id, word="ethics", meaning="nghia0, đạo đức học")
    db_session.add_all([flagged, twin])
    db_session.commit()

    for _ in range(5):
        rows = client.get(f"/api/v1/word-sets/{ws.id}/quiz?limit=20", headers=headers).json()
        assert flagged.id not in {r["item_id"] for r in rows}          # không làm câu hỏi
        for r in rows:
            assert len(set(r["options"])) == 4
            if r["word"] == "word0":                                 # nghĩa "nghia0"
                assert twin.meaning not in r["options"]              # nhiễu không trùng nghĩa

    ids = [flagged.id, items[1].id]
    rows = client.post("/api/v1/sessions/quiz-questions", json={"item_ids": ids}, headers=headers).json()
    assert [r["item_id"] for r in rows] == [items[1].id]             # từ bị cờ -> thẻ lật thường


# --- bug #9 (2026-10-26): mỗi đáp án chỉ MỘT nghĩa ----------------------------

def test_pure_answer_label_lay_nghia_chinh():
    from app.services.quiz_service import answer_label
    assert answer_label("lợi, lợi ích, bổ ích") == "lợi"
    assert answer_label("Số liệu, dữ liệu") == "số liệu"              # hạ hoa đầu, khỏi lộ đáp án
    assert answer_label("Thống nhất/ nhất quán") == "thống nhất"
    assert answer_label("hốc thường (thường để đặt tượng...)") == "hốc thường"
    assert answer_label("chủ yếu; quan trọng") == "chủ yếu"
    assert answer_label("AI, trí tuệ nhân tạo") == "AI"               # viết tắt giữ nguyên
    assert answer_label("sự kết hợp") == "sự kết hợp"
    # nhãn trong ngoặc đứng trước dấu ":" (nghĩa sửa tay) -> không để sót ":" ở đầu
    assert answer_label("(Mạo từ): một + Danh từ") == "một + Danh từ"
    assert answer_label("(ĐT Nguyên mẫu): đến, tới") == "đến"
    assert answer_label("(mạo từ xác định) cái đó, người ấy") == "cái đó"
    assert answer_label("(lóng) buổi diễn ngắn -> việc ngắn hạn") == "buổi diễn ngắn -> việc ngắn hạn"


def test_pure_nhieu_khac_nhau_nhung_cung_nghia_chinh_bi_loai():
    pool = [("bàn, bàn học", "noun", True), ("bàn, cái bàn", "noun", True),
            ("ghế", "noun", True), ("cửa", "noun", True)]
    from app.services.quiz_service import answer_label
    for _ in range(20):
        got = pick_distractors("đạo đức", "noun", pool)
        assert got is not None
        assert len({answer_label(g) for g in got}) == 3


def test_quiz_moi_dap_an_mot_nghia(client, db_session):
    _, headers, ws, items = _setup(db_session, "quiz.onesense@example.com", n_items=5)
    for it in items:
        it.meaning = f"{it.meaning}, nghĩa phụ {it.id}"
    db_session.commit()

    rows = client.get(f"/api/v1/word-sets/{ws.id}/quiz?limit=20", headers=headers).json()
    assert rows
    for r in rows:
        assert all("," not in o for o in r["options"])
        assert r["options"][r["correct_index"]] == next(
            it.meaning.split(",")[0] for it in items if it.id == r["item_id"])

    rows = client.post("/api/v1/sessions/quiz-questions",
                       json={"item_ids": [it.id for it in items]}, headers=headers).json()
    assert rows and all("," not in o for r in rows for o in r["options"])
