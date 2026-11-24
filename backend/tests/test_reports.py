"""UC-24 — báo cáo bộ từ vi phạm."""
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.item import Item
from app.models.report import Report
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _public_set(db_session, owner_id, name):
    ws = WordSet(owner_id=owner_id, name=name, is_public=True)
    db_session.add(ws)
    db_session.flush()
    db_session.add(Item(word_set_id=ws.id, word="w", meaning="m"))
    db_session.commit()
    db_session.refresh(ws)
    return ws


def _count_reports(db_session, target_id):
    return db_session.execute(
        select(func.count()).select_from(Report).where(Report.target_id == target_id)
    ).scalar_one()


def test_report_word_set(client, db_session):
    owner, _ = _user(db_session, "rp.own1@example.com")
    ws = _public_set(db_session, owner.id, "Spam set")
    _, headers = _user(db_session, "rp.lrn1@example.com")

    r = client.post(f"/api/v1/discover/{ws.id}/report",
                    json={"reason": "spam", "description": "Toàn quảng cáo"}, headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["target_type"] == "word_set" and body["target_id"] == ws.id
    assert body["status"] == "pending" and body["merged"] is False
    assert _count_reports(db_session, ws.id) == 1


def test_duplicate_report_is_merged(client, db_session):
    """E1: cùng người báo cáo lại cùng bộ -> gộp, không tạo bản ghi mới."""
    owner, _ = _user(db_session, "rp.own2@example.com")
    ws = _public_set(db_session, owner.id, "Dup set")
    _, headers = _user(db_session, "rp.lrn2@example.com")

    first = client.post(f"/api/v1/discover/{ws.id}/report", json={"reason": "spam"}, headers=headers).json()
    second = client.post(f"/api/v1/discover/{ws.id}/report",
                         json={"reason": "copyright"}, headers=headers).json()

    assert second["id"] == first["id"] and second["merged"] is True
    assert second["reason"] == "spam"  # giữ báo cáo gốc
    assert _count_reports(db_session, ws.id) == 1


def test_two_users_report_same_set(client, db_session):
    owner, _ = _user(db_session, "rp.own3@example.com")
    ws = _public_set(db_session, owner.id, "Bad set")
    _, h1 = _user(db_session, "rp.lrn3a@example.com")
    _, h2 = _user(db_session, "rp.lrn3b@example.com")

    client.post(f"/api/v1/discover/{ws.id}/report", json={"reason": "spam"}, headers=h1)
    client.post(f"/api/v1/discover/{ws.id}/report", json={"reason": "offensive"}, headers=h2)
    assert _count_reports(db_session, ws.id) == 2


def test_report_invalid_reason_and_missing_set(client, db_session):
    owner, _ = _user(db_session, "rp.own4@example.com")
    ws = _public_set(db_session, owner.id, "Gone set")
    _, headers = _user(db_session, "rp.lrn4@example.com")

    assert client.post(f"/api/v1/discover/{ws.id}/report",
                       json={"reason": "khong_ton_tai"}, headers=headers).status_code == 422

    ws.is_public = False
    db_session.commit()
    assert client.post(f"/api/v1/discover/{ws.id}/report",
                       json={"reason": "spam"}, headers=headers).status_code == 404
