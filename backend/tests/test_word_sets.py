import io
import pytest
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.item import Item
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.services.mastery_service import build_history

from app.core.security import create_access_token
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _make_user(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(
            email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"
        ),
    )
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _create_set(client, headers, **overrides) -> dict:
    payload = {"name": "Bo tu 1", **overrides}
    resp = client.post("/api/v1/word-sets", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_item(client, headers, ws_id, word="hello", meaning="xin chao") -> dict:
    resp = client.post(
        f"/api/v1/word-sets/{ws_id}/items",
        json={"word": word, "meaning": meaning},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------- UC-13: tạo/sửa/xóa bộ từ ----------


def test_create_word_set(client, db_session):
    _, headers = _make_user(db_session, "uc13.a@example.com")
    body = _create_set(client, headers, name="TOEIC 500", category="TOEIC", difficulty="beginner")
    assert body["name"] == "TOEIC 500"
    assert body["category"] == "TOEIC"
    assert body["is_public"] is False
    assert body["item_count"] == 0


def test_create_word_set_missing_name(client, db_session):
    _, headers = _make_user(db_session, "uc13.b@example.com")
    resp = client.post("/api/v1/word-sets", json={"name": ""}, headers=headers)
    assert resp.status_code == 422


def test_update_word_set(client, db_session):
    _, headers = _make_user(db_session, "uc13.c@example.com")
    ws = _create_set(client, headers)
    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}",
        json={"name": "Doi ten", "description": "mo ta moi"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Doi ten"
    assert resp.json()["description"] == "mo ta moi"


def test_delete_word_set_soft(client, db_session):
    _, headers = _make_user(db_session, "uc13.d@example.com")
    ws = _create_set(client, headers)
    resp = client.delete(f"/api/v1/word-sets/{ws['id']}", headers=headers)
    assert resp.status_code == 204

    # không còn xuất hiện trong thư viện
    assert client.get("/api/v1/word-sets", headers=headers).json() == []
    # nhưng vẫn còn trong DB với deleted_at (xóa mềm)
    row = db_session.get(WordSet, ws["id"])
    assert row is not None and row.deleted_at is not None


def test_word_set_ownership_isolation(client, db_session):
    _, headers_a = _make_user(db_session, "uc13.owner@example.com")
    _, headers_b = _make_user(db_session, "uc13.other@example.com")
    ws = _create_set(client, headers_a)

    assert client.get(f"/api/v1/word-sets/{ws['id']}", headers=headers_b).status_code == 404
    assert client.patch(
        f"/api/v1/word-sets/{ws['id']}", json={"name": "x"}, headers=headers_b
    ).status_code == 404
    assert client.delete(f"/api/v1/word-sets/{ws['id']}", headers=headers_b).status_code == 404


# ---------- UC-16: thư viện bộ từ ----------


def test_library_lists_owned_with_counts(client, db_session):
    _, headers = _make_user(db_session, "uc16.a@example.com")
    ws = _create_set(client, headers, name="Set A")
    _add_item(client, headers, ws["id"])
    _add_item(client, headers, ws["id"], word="bye", meaning="tam biet")
    _create_set(client, headers, name="Set B")

    library = client.get("/api/v1/word-sets", headers=headers).json()
    assert len(library) == 2
    by_name = {s["name"]: s for s in library}
    assert by_name["Set A"]["item_count"] == 2
    assert by_name["Set B"]["item_count"] == 0


def test_library_counts_learning_separately_from_mastered(client, db_session):
    """Thanh tiến độ 3 nấc: đã thuộc (BR-01) / đang học / chưa học."""
    user, headers = _make_user(db_session, "uc16.learn@example.com")
    ws = _create_set(client, headers, name="Set L")
    a = _add_item(client, headers, ws["id"], word="a", meaning="a")
    b = _add_item(client, headers, ws["id"], word="b", meaning="b")
    _add_item(client, headers, ws["id"], word="c", meaning="c")
    now = datetime.now(timezone.utc)
    db_session.add(KnowledgeState(user_id=user.id, item_id=a["id"], mastery=0.95, last_updated=now))
    db_session.add(KnowledgeState(user_id=user.id, item_id=b["id"], mastery=0.4, last_updated=now))
    for _ in range(3):
        db_session.add(Interaction(user_id=user.id, item_id=a["id"], is_correct=True, answered_at=now))
    db_session.commit()

    row = next(s for s in client.get("/api/v1/word-sets", headers=headers).json() if s["name"] == "Set L")
    assert row["item_count"] == 3
    assert row["mastered_count"] == 1
    assert row["learning_count"] == 1


def test_library_empty(client, db_session):
    _, headers = _make_user(db_session, "uc16.b@example.com")
    assert client.get("/api/v1/word-sets", headers=headers).json() == []


# ---------- UC-14: thêm/sửa/xóa từ ----------


def test_create_item(client, db_session):
    _, headers = _make_user(db_session, "uc14.a@example.com")
    ws = _create_set(client, headers)
    body = _add_item(client, headers, ws["id"], word="cat", meaning="con meo")
    assert body["word"] == "cat"
    assert body["word_set_id"] == ws["id"]


def test_create_item_missing_required(client, db_session):
    _, headers = _make_user(db_session, "uc14.b@example.com")
    ws = _create_set(client, headers)
    assert client.post(
        f"/api/v1/word-sets/{ws['id']}/items", json={"word": "", "meaning": "x"}, headers=headers
    ).status_code == 422
    assert client.post(
        f"/api/v1/word-sets/{ws['id']}/items", json={"word": "x", "meaning": ""}, headers=headers
    ).status_code == 422


def test_update_item(client, db_session):
    _, headers = _make_user(db_session, "uc14.c@example.com")
    ws = _create_set(client, headers)
    item = _add_item(client, headers, ws["id"])
    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}/items/{item['id']}",
        json={"word": "hi", "meaning": "chao", "phonetic": "/haɪ/"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["word"] == "hi"
    assert resp.json()["phonetic"] == "/haɪ/"


@pytest.mark.parametrize("changes", [
    {"word": "banana", "meaning": "chuối"}, {"meaning": "a different sense"}, {"part_of_speech": "verb"},
])
def test_edit_learned_word_preserves_history_and_resets_replacement(client, db_session, changes):
    user, headers = _make_user(db_session, "uc14.version@example.com")
    ws = _create_set(client, headers)
    old = _add_item(client, headers, ws["id"], word="apple", meaning="táo")
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Interaction(user_id=user.id, item_id=old["id"], is_correct=True,
                    exercise_format="typing", answered_at=now),
        KnowledgeState(user_id=user.id, item_id=old["id"], mastery=0.95, last_updated=now),
        ReviewSchedule(user_id=user.id, item_id=old["id"], next_review_at=now, interval_days=7),
    ])
    db_session.commit()
    response = client.patch(
        f"/api/v1/word-sets/{ws['id']}/items/{old['id']}",
        json={"word": "apple", "meaning": "táo", **changes}, headers=headers,
    )
    assert response.status_code == 200, response.text
    replacement = response.json()
    assert replacement["id"] != old["id"]
    original = db_session.get(Item, old["id"])
    assert original.word == "apple" and original.deleted_at is not None
    assert original.meaning == "táo" and original.part_of_speech is None
    assert build_history(db_session, user.id)[0] == [("apple", 1)]
    for model in (Interaction, KnowledgeState, ReviewSchedule):
        assert db_session.execute(select(model).where(model.item_id == replacement["id"])).first() is None
    live = client.get(f"/api/v1/word-sets/{ws['id']}/items", headers=headers).json()
    assert [row["id"] for row in live] == [replacement["id"]]


def test_edit_learned_word_pronunciation_keeps_identity(client, db_session):
    user, headers = _make_user(db_session, "uc14.phonetic@example.com")
    ws = _create_set(client, headers)
    old = _add_item(client, headers, ws["id"])
    db_session.add(Interaction(user_id=user.id, item_id=old["id"], is_correct=True,
                               answered_at=datetime.now(timezone.utc)))
    db_session.commit()
    response = client.patch(
        f"/api/v1/word-sets/{ws['id']}/items/{old['id']}",
        json={"word": old["word"], "meaning": old["meaning"], "phonetic": "/hello/"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["id"] == old["id"]
    assert db_session.get(Item, old["id"]).deleted_at is None


def test_edit_during_active_session_does_not_relabel_issued_question(client, db_session):
    _, headers = _make_user(db_session, "uc14.active@example.com")
    ws = _create_set(client, headers)
    old = _add_item(client, headers, ws["id"])
    sid = client.post("/api/v1/sessions", headers=headers,
        json={"word_set_id": ws["id"], "mode": "typing"}).json()["id"]
    changed = client.patch(f"/api/v1/word-sets/{ws['id']}/items/{old['id']}",
        headers=headers, json={"word": "new", "meaning": "new meaning"})
    assert changed.status_code == 200
    assert changed.json()["id"] != old["id"]
    stale = client.post(f"/api/v1/sessions/{sid}/answer", headers=headers,
        json={"item_id": old["id"], "answer": old["word"]})
    assert stale.status_code == 404
    assert db_session.query(Interaction).filter_by(session_id=sid).count() == 0


def test_delete_item_soft(client, db_session):
    _, headers = _make_user(db_session, "uc14.d@example.com")
    ws = _create_set(client, headers)
    item = _add_item(client, headers, ws["id"])
    assert client.delete(
        f"/api/v1/word-sets/{ws['id']}/items/{item['id']}", headers=headers
    ).status_code == 204

    items = client.get(f"/api/v1/word-sets/{ws['id']}/items", headers=headers).json()
    assert items == []
    # item_count trên bộ từ cũng về 0
    assert client.get(f"/api/v1/word-sets/{ws['id']}", headers=headers).json()["item_count"] == 0


def test_item_ops_on_foreign_set_404(client, db_session):
    _, headers_a = _make_user(db_session, "uc14.owner@example.com")
    _, headers_b = _make_user(db_session, "uc14.other@example.com")
    ws = _create_set(client, headers_a)
    item = _add_item(client, headers_a, ws["id"])

    assert client.get(f"/api/v1/word-sets/{ws['id']}/items", headers=headers_b).status_code == 404
    assert client.post(
        f"/api/v1/word-sets/{ws['id']}/items", json={"word": "x", "meaning": "y"}, headers=headers_b
    ).status_code == 404
    assert client.patch(
        f"/api/v1/word-sets/{ws['id']}/items/{item['id']}",
        json={"word": "x", "meaning": "y"},
        headers=headers_b,
    ).status_code == 404


# ---------- UC-15: import CSV ----------


def _import_csv(client, headers, ws_id, content: str):
    return client.post(
        f"/api/v1/word-sets/{ws_id}/items/import",
        files={"file": ("words.csv", io.BytesIO(content.encode("utf-8")), "text/csv")},
        headers=headers,
    )


def test_import_csv_all_valid(client, db_session):
    _, headers = _make_user(db_session, "uc15.a@example.com")
    ws = _create_set(client, headers)
    csv_content = (
        "word,phonetic,part_of_speech,meaning,example\n"
        "apple,/ˈæpəl/,noun,quả táo,I eat an apple.\n"
        "run,/rʌn/,verb,chạy,I run fast.\n"
    )
    resp = _import_csv(client, headers, ws["id"], csv_content)
    assert resp.status_code == 200
    report = resp.json()
    assert report["imported"] == 2
    assert report["errors"] == []
    assert client.get(f"/api/v1/word-sets/{ws['id']}", headers=headers).json()["item_count"] == 2


def test_import_csv_partial_valid(client, db_session):
    _, headers = _make_user(db_session, "uc15.b@example.com")
    ws = _create_set(client, headers)
    csv_content = (
        "word,phonetic,part_of_speech,meaning,example\n"
        "apple,,,quả táo,\n"
        ",,,thiếu word,\n"  # dòng lỗi: thiếu word
        "run,,,,\n"  # dòng lỗi: thiếu meaning
    )
    resp = _import_csv(client, headers, ws["id"], csv_content)
    assert resp.status_code == 200
    report = resp.json()
    assert report["imported"] == 1
    assert len(report["errors"]) == 2
    assert {e["row"] for e in report["errors"]} == {2, 3}


def test_import_csv_missing_columns(client, db_session):
    _, headers = _make_user(db_session, "uc15.c@example.com")
    ws = _create_set(client, headers)
    resp = _import_csv(client, headers, ws["id"], "foo,bar\n1,2\n")
    assert resp.status_code == 422


# ---------- UC-17: công khai / ẩn bộ từ ----------


def test_publish_success(client, db_session):
    _, headers = _make_user(db_session, "uc17.a@example.com")
    ws = _create_set(client, headers, category="General", difficulty="beginner")
    _add_item(client, headers, ws["id"])

    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}/publish", json={"is_public": True}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is True


def test_publish_rejected_no_items(client, db_session):
    _, headers = _make_user(db_session, "uc17.b@example.com")
    ws = _create_set(client, headers, category="General", difficulty="beginner")
    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}/publish", json={"is_public": True}, headers=headers
    )
    assert resp.status_code == 400


def test_publish_rejected_missing_metadata(client, db_session):
    _, headers = _make_user(db_session, "uc17.c@example.com")
    ws = _create_set(client, headers)  # không có category/difficulty
    _add_item(client, headers, ws["id"])
    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}/publish", json={"is_public": True}, headers=headers
    )
    assert resp.status_code == 400


def test_unpublish_no_conditions(client, db_session):
    _, headers = _make_user(db_session, "uc17.d@example.com")
    ws = _create_set(client, headers, category="General", difficulty="beginner")
    _add_item(client, headers, ws["id"])
    client.patch(f"/api/v1/word-sets/{ws['id']}/publish", json={"is_public": True}, headers=headers)

    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}/publish", json={"is_public": False}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["is_public"] is False


# ---------- Auth ----------


def test_word_sets_require_auth(client):
    assert client.get("/api/v1/word-sets").status_code == 401
    assert client.post("/api/v1/word-sets", json={"name": "x"}).status_code == 401
