"""Bug #8/#9 — đồng bộ nội dung bộ nền đã sửa vào DB đang chạy (sync_seed_content)."""
from datetime import datetime, timezone

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.word_set import WordSet
from app.scripts.sync_seed_content import sync_seed_content

from tests.test_sessions import _setup

PAYLOAD = {"word_sets": [{"name": "A1 · Từ 1–50", "items": [
    {"word": "say", "meaning": "nói, bảo", "phonetic": "/sei/", "part_of_speech": "verb",
     "meaning_source": "llm", "meaning_confidence": "llm", "example": "", "example_source": ""},
    {"word": "ethical", "meaning": "đạo đức", "phonetic": "/'eθikəl/", "part_of_speech": "adjective",
     "meaning_source": "fvdp", "meaning_confidence": "needs-review", "example": "", "example_source": ""},
]}]}


def _old(word_set_id: int, word: str, meaning: str, phonetic: str, source: str | None = "fvdp") -> Item:
    return Item(word_set_id=word_set_id, word=word, meaning=meaning, phonetic=phonetic,
                part_of_speech="noun", meaning_source=source, meaning_confidence="needs-review")


def test_dong_bo_tai_cho_giu_lich_su_va_cho_nguoi_hoc_tu_sua(db_session):
    owner, _, _, _ = _setup(db_session, "sync.owner@example.com", n_items=0)
    learner, _, _, _ = _setup(db_session, "sync.learner@example.com", n_items=0)

    original = WordSet(owner_id=owner.id, name="A1 · Từ 1–50", category="Cốt lõi",
                       difficulty="beginner", is_public=True)
    db_session.add(original)
    db_session.flush()
    copy = WordSet(owner_id=learner.id, name="A1 · Từ 1–50", category="Cốt lõi",
                   difficulty="beginner", origin_set_id=original.id)
    db_session.add(copy)
    db_session.flush()

    o_say = _old(original.id, "say", "vải chéo", "/sei/")
    o_eth = _old(original.id, "ethical", "đạo đức", "/'eθik/")
    c_say = _old(copy.id, "say", "vải chéo", "/sei/")
    c_eth = _old(copy.id, "ethical", "đạo đức", "/tự ghi/")               # người học tự sửa IPA
    mine = _old(copy.id, "say2", "chữ của tôi", "/x/", source=None)       # người học tự nhập
    db_session.add_all([o_say, o_eth, c_say, c_eth, mine])
    db_session.flush()
    db_session.add(Interaction(user_id=learner.id, item_id=c_say.id, is_correct=True,
                               answered_at=datetime.now(timezone.utc)))
    db_session.commit()

    dry = sync_seed_content(db_session, PAYLOAD, apply=False)
    assert dry["item cập nhật"] == 4
    db_session.refresh(c_say)
    assert c_say.meaning == "vải chéo"                                     # chạy thử: không ghi

    stats = sync_seed_content(db_session, PAYLOAD, apply=True)
    for it in (o_say, o_eth, c_say, c_eth, mine):
        db_session.refresh(it)
    assert (c_say.meaning, c_say.part_of_speech, c_say.meaning_source) == ("nói, bảo", "verb", "llm")
    assert c_say.deleted_at is None                                        # tại chỗ, không tạo item mới
    assert db_session.query(Interaction).filter_by(item_id=c_say.id).count() == 1
    assert o_eth.phonetic == "/'eθikəl/"                                   # bug #8
    assert c_eth.phonetic == "/tự ghi/" and c_eth.part_of_speech == "adjective"
    assert stats["giữ chỗ người học tự sửa"] == 1
    assert mine.meaning == "chữ của tôi"


def test_dong_bo_ban_dich_vi_du_bo_qua_cau_nguoi_hoc_tu_sua(db_session):
    """Bản dịch câu ví dụ chỉ gắn vào item còn giữ đúng câu gốc."""
    owner, _, _, _ = _setup(db_session, "exvi.owner@example.com", n_items=0)
    learner, _, _, _ = _setup(db_session, "exvi.learner@example.com", n_items=0)
    payload = {"word_sets": [{"name": "A1 · Từ 1–50", "items": [
        {"word": "cat", "meaning": "con mèo", "meaning_source": "fvdp",
         "example": "The cat sleeps.", "example_source": "llm", "example_vi": "Con mèo ngủ."},
    ]}]}
    original = WordSet(owner_id=owner.id, name="A1 · Từ 1–50", category="Cốt lõi",
                       difficulty="beginner", is_public=True)
    db_session.add(original)
    db_session.flush()
    kept = WordSet(owner_id=learner.id, name="A1 · Từ 1–50", category="Cốt lõi",
                   difficulty="beginner", origin_set_id=original.id)
    db_session.add(kept)
    db_session.flush()

    def _cat(word_set_id: int, example: str) -> Item:
        return Item(word_set_id=word_set_id, word="cat", meaning="con mèo", meaning_source="fvdp",
                    example=example, example_source="llm")

    o_cat = _cat(original.id, "The cat sleeps.")
    c_cat = _cat(kept.id, "My cat is lazy.")                               # người học tự sửa câu
    db_session.add_all([o_cat, c_cat])
    db_session.commit()

    sync_seed_content(db_session, payload, apply=True)
    db_session.refresh(o_cat)
    db_session.refresh(c_cat)
    assert o_cat.example_vi == "Con mèo ngủ."
    assert c_cat.example == "My cat is lazy." and c_cat.example_vi is None
