from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token
from app.models.item import Item
from app.models.review_schedule import ReviewSchedule
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services.gamification_service import default_daily_item_goal
from app.services.auth_service import register_user

VALID_PAYLOAD = {
    "email": "dash.user@example.com",
    "password": "Abcd1234",
    "password_confirm": "Abcd1234",
    "display_name": "Dash User",
}


def _create_user_and_token(db_session):
    user = register_user(db_session, RegisterRequest(**VALID_PAYLOAD))
    token = create_access_token(user.id, user.role)
    return user, token


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_new_user_all_zero(client, db_session):
    _, token = _create_user_and_token(db_session)

    response = client.get("/api/v1/dashboard", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["xp"] == 0
    assert body["level"] == 1
    assert body["xp_into_level"] == 0
    assert body["xp_for_next_level"] == 100
    assert body["streak_count"] == 0
    assert body["items_mastered"] == 0
    assert body["word_set_count"] == 0
    assert body["review_due_count"] == 0
    # UC-10 luồng 1a: chưa đặt mục tiêu -> mặc định 10 từ/ngày
    assert body["daily_item_goal"] == default_daily_item_goal()


def test_dashboard_reflects_progress_and_level(client, db_session):
    user, token = _create_user_and_token(db_session)
    progress = db_session.query(UserProgress).filter_by(user_id=user.id).one()
    progress.xp = 250
    progress.streak_count = 5
    progress.items_mastered = 3
    db_session.commit()

    response = client.get("/api/v1/dashboard", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["xp"] == 250
    assert body["level"] == 3  # 250 // 100 + 1
    assert body["xp_into_level"] == 50  # 250 % 100
    assert body["streak_count"] == 5
    assert body["items_mastered"] == 0  # stale cache must not replace BR-01 evidence


def test_dashboard_daily_goal_from_settings(client, db_session):
    user, token = _create_user_and_token(db_session)
    settings = db_session.query(UserSettings).filter_by(user_id=user.id).one()
    settings.daily_item_goal = 20
    db_session.commit()

    response = client.get("/api/v1/dashboard", headers=_auth_header(token))

    assert response.json()["daily_item_goal"] == 20


def test_dashboard_word_set_count_excludes_soft_deleted(client, db_session):
    user, token = _create_user_and_token(db_session)
    db_session.add(WordSet(owner_id=user.id, name="Bo tu 1"))
    db_session.add(WordSet(owner_id=user.id, name="Bo tu 2"))
    db_session.add(
        WordSet(owner_id=user.id, name="Da xoa", deleted_at=datetime.now(timezone.utc))
    )
    db_session.commit()

    response = client.get("/api/v1/dashboard", headers=_auth_header(token))

    assert response.json()["word_set_count"] == 2


def test_dashboard_review_due_count(client, db_session):
    user, token = _create_user_and_token(db_session)
    word_set = WordSet(owner_id=user.id, name="Bo tu")
    db_session.add(word_set)
    db_session.flush()
    item_due = Item(word_set_id=word_set.id, word="due", meaning="den han")
    item_future = Item(word_set_id=word_set.id, word="future", meaning="tuong lai")
    db_session.add_all([item_due, item_future])
    db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add(
        ReviewSchedule(
            user_id=user.id, item_id=item_due.id, next_review_at=now - timedelta(hours=1)
        )
    )
    db_session.add(
        ReviewSchedule(
            user_id=user.id, item_id=item_future.id, next_review_at=now + timedelta(days=1)
        )
    )
    db_session.commit()

    response = client.get("/api/v1/dashboard", headers=_auth_header(token))

    assert response.json()["review_due_count"] == 1  # chỉ item đã đến hạn


def test_dashboard_requires_auth(client):
    response = client.get("/api/v1/dashboard")

    assert response.status_code == 401
