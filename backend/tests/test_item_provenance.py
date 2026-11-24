"""Nguồn gốc nghĩa/ví dụ của ITEM: meaning_confidence, meaning_source, example_source.

Bộ từ nền lấy nghĩa từ một bản số hoá từ điển cũ nên nghĩa đầu tiên đôi khi là
nghĩa cổ (`service` -> "cây thanh lương trà"). Bước dựng dữ liệu gắn cờ những
chỗ đó; các test dưới đây giữ cho cờ không bị mất hoặc bị nói dối trên đường từ
file JSON tới màn hình người học.
"""
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.schemas.item import ItemCreateRequest, ItemProvenance, ItemUpdateRequest
from app.services import discover_service, item_service
from app.services.auth_service import register_user

PASSWORD = "Abcd1234"


def _user(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(email=email, password=PASSWORD, password_confirm=PASSWORD,
                        display_name="U"),
    )
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _word_set(db_session, owner, name="Set", public=False):
    ws = WordSet(owner_id=owner.id, name=name, category="Gen", difficulty="beginner",
                 cefr_level="A1", is_public=public)
    db_session.add(ws)
    db_session.flush()
    return ws


def test_seed_luu_duoc_co_do_tin_cay(db_session):
    """Luồng seed truyền `provenance` -> ba cột được ghi xuống DB."""
    user, _ = _user(db_session, "prov1@example.com")
    ws = _word_set(db_session, user)

    item_service.create_item(
        db_session, user, ws.id,
        ItemCreateRequest(word="service", meaning="cây thanh lương trà"),
        provenance=ItemProvenance(meaning_confidence="needs-review",
                                  meaning_source="fvdp", example_source="llm"),
    )

    row = db_session.execute(select(Item).where(Item.word == "service")).scalar_one()
    assert row.meaning_confidence == "needs-review"
    assert row.meaning_source == "fvdp"
    assert row.example_source == "llm"


def test_item_nguoi_dung_tu_nhap_khong_bi_gan_co(db_session):
    """Không truyền provenance -> NULL. Không gắn cờ lên chữ của chính người học."""
    user, _ = _user(db_session, "prov2@example.com")
    ws = _word_set(db_session, user)

    item_service.create_item(
        db_session, user, ws.id, ItemCreateRequest(word="tu", meaning="nghia cua toi"),
    )

    row = db_session.execute(select(Item).where(Item.word == "tu")).scalar_one()
    assert row.meaning_confidence is None
    assert row.meaning_source is None


def test_sua_nghia_thi_go_co_cu(db_session):
    """Người học viết lại nghĩa -> cờ của TỪ ĐIỂN không còn nói về nội dung này.

    Giữ lại cờ cũ sẽ hiện "chưa đối chứng" trên chính chữ họ vừa sửa, hoặc tệ
    hơn là dán nhãn đã-đối-chứng lên nội dung chưa ai đối chứng.
    """
    user, _ = _user(db_session, "prov3@example.com")
    ws = _word_set(db_session, user)
    created = item_service.create_item(
        db_session, user, ws.id,
        ItemCreateRequest(word="main", meaning="cuộc chọi gà"),
        provenance=ItemProvenance(meaning_confidence="needs-review", meaning_source="fvdp"),
    )

    item_service.update_item(
        db_session, user, ws.id, created.id,
        ItemUpdateRequest(word="main", meaning="chính, chủ yếu"),
    )

    row = db_session.execute(
        select(Item).where(Item.word == "main", Item.deleted_at.is_(None))
    ).scalar_one()
    assert row.meaning == "chính, chủ yếu"
    assert row.meaning_confidence is None
    assert row.meaning_source == "user"


def test_sua_truong_khac_thi_giu_nguyen_co(db_session):
    """Chỉ sửa phiên âm thì nghĩa vẫn là nghĩa cũ -> cờ phải còn."""
    user, _ = _user(db_session, "prov4@example.com")
    ws = _word_set(db_session, user)
    created = item_service.create_item(
        db_session, user, ws.id,
        ItemCreateRequest(word="stage", meaning="bệ, dài", phonetic="/steid3/"),
        provenance=ItemProvenance(meaning_confidence="needs-review", meaning_source="fvdp"),
    )

    item_service.update_item(
        db_session, user, ws.id, created.id,
        ItemUpdateRequest(word="stage", meaning="bệ, dài", phonetic="/steɪdʒ/"),
    )

    row = db_session.execute(select(Item).where(Item.word == "stage")).scalar_one()
    assert row.meaning_confidence == "needs-review"
    assert row.meaning_source == "fvdp"


def test_tai_bo_tu_ve_thi_mang_theo_co(db_session):
    """Q1 — snapshot phải sao cả nguồn gốc.

    Bản sao có đúng nội dung của bản gốc thì phải có đúng mức tin cậy của bản
    gốc; bỏ ba trường này là tải về xong cảnh báo biến mất trong khi nghĩa y
    nguyên.
    """
    owner, _ = _user(db_session, "prov5@example.com")
    learner, _ = _user(db_session, "prov6@example.com")
    ws = _word_set(db_session, owner, name="Bộ công khai", public=True)
    item_service.create_item(
        db_session, owner, ws.id,
        ItemCreateRequest(word="able", meaning="có năng lực, có tài"),
        provenance=ItemProvenance(meaning_confidence="needs-review",
                                  meaning_source="fvdp", example_source="llm"),
    )

    clone = discover_service.clone_word_set(db_session, learner, ws.id)

    copied = db_session.execute(
        select(Item).where(Item.word_set_id == clone.id)
    ).scalar_one()
    assert copied.meaning_confidence == "needs-review"
    assert copied.meaning_source == "fvdp"
    assert copied.example_source == "llm"


def test_api_khong_cho_nguoi_dung_tu_chung_nhan(db_session, client):
    """`meaning_confidence` không nằm trong ItemCreateRequest.

    Gửi kèm qua API thì Pydantic bỏ qua, item vẫn NULL — người học không tự
    dán nhãn "đã đối chứng" lên nghĩa của mình được.
    """
    user, headers = _user(db_session, "prov7@example.com")
    ws = _word_set(db_session, user)
    db_session.commit()

    resp = client.post(
        f"/api/v1/word-sets/{ws.id}/items",
        json={"word": "fake", "meaning": "tu bia", "meaning_confidence": "confirmed"},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["meaning_confidence"] is None


def test_ban_dich_vi_du_theo_item_va_ban_sao(db_session):
    """Bản dịch câu ví dụ seed vào DB và đi theo bản sao khi tải bộ về (Q1)."""
    owner, _ = _user(db_session, "exvi1@example.com")
    learner, _ = _user(db_session, "exvi2@example.com")
    ws = _word_set(db_session, owner, name="Bộ có dịch", public=True)
    item_service.create_item(
        db_session, owner, ws.id,
        ItemCreateRequest(word="cat", meaning="con mèo", example="The cat sleeps."),
        provenance=ItemProvenance(example_source="llm", example_vi="Con mèo ngủ."),
    )

    clone = discover_service.clone_word_set(db_session, learner, ws.id)

    copied = db_session.execute(select(Item).where(Item.word_set_id == clone.id)).scalar_one()
    assert copied.example_vi == "Con mèo ngủ."


def test_sua_cau_vi_du_thi_bo_ban_dich_cu(db_session):
    """Câu mới thì bản dịch của câu cũ sai — bỏ đi; sửa trường khác thì giữ."""
    user, _ = _user(db_session, "exvi3@example.com")
    ws = _word_set(db_session, user)
    created = item_service.create_item(
        db_session, user, ws.id,
        ItemCreateRequest(word="dog", meaning="con chó", example="The dog barks."),
        provenance=ItemProvenance(example_source="fvdp", example_vi="Con chó sủa."),
    )

    item_service.update_item(
        db_session, user, ws.id, created.id,
        ItemUpdateRequest(word="dog", meaning="con chó", phonetic="/dɒɡ/", example="The dog barks."),
    )
    row = db_session.execute(select(Item).where(Item.word == "dog")).scalar_one()
    assert row.example_vi == "Con chó sủa."

    item_service.update_item(
        db_session, user, ws.id, created.id,
        ItemUpdateRequest(word="dog", meaning="con chó", example="My dog is old."),
    )
    db_session.refresh(row)
    assert row.example_vi is None


def test_api_khong_nhan_ban_dich_tu_nguoi_dung(db_session, client):
    """`example_vi` đi cùng nguồn câu ví dụ (ItemProvenance), API công khai bỏ qua."""
    user, headers = _user(db_session, "exvi4@example.com")
    ws = _word_set(db_session, user)
    db_session.commit()

    resp = client.post(
        f"/api/v1/word-sets/{ws.id}/items",
        json={"word": "x", "meaning": "y", "example": "An x.", "example_vi": "Một x."},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    assert resp.json()["example_vi"] is None
